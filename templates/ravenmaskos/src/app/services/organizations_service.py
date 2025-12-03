"""Organization management business logic service."""

import re
import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.tenant import ApiKey, Organization, User
from app.schemas.organizations import (
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationStatsResponse,
    OrganizationUpdate,
)

logger = get_logger(__name__)


class OrganizationError(Exception):
    """Base organization error."""

    def __init__(self, message: str, code: str = "org_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class OrganizationNotFoundError(OrganizationError):
    """Organization not found."""

    def __init__(self):
        super().__init__("Organization not found", "org_not_found")


class SlugExistsError(OrganizationError):
    """Organization slug already exists."""

    def __init__(self):
        super().__init__("Organization slug already exists", "slug_exists")


def _generate_slug(name: str) -> str:
    """Generate URL-safe slug from organization name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    suffix = secrets.token_hex(4)
    return f"{slug[:50]}-{suffix}"


async def list_organizations(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    is_active: bool | None = None,
) -> OrganizationListResponse:
    """List all organizations (platform admin only).

    Args:
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of orgs per page
        search: Optional search term for name/slug
        is_active: Optional filter for active status

    Returns:
        Paginated list of organizations
    """
    query = select(Organization).where(Organization.deleted_at.is_(None))

    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Organization.name.ilike(search_term)) | (Organization.slug.ilike(search_term))
        )

    if is_active is not None:
        query = query.where(Organization.is_active == is_active)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Organization.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    orgs = result.scalars().all()

    return OrganizationListResponse(
        organizations=[OrganizationResponse.model_validate(o) for o in orgs],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(orgs)) < total,
    )


async def get_organization(
    db: AsyncSession,
    org_id: str,
) -> OrganizationResponse:
    """Get an organization by ID.

    Raises:
        OrganizationNotFoundError: If org not found
    """
    result = await db.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()

    if not org:
        raise OrganizationNotFoundError()

    return OrganizationResponse.model_validate(org)


async def get_organization_by_slug(
    db: AsyncSession,
    slug: str,
) -> OrganizationResponse:
    """Get an organization by slug.

    Raises:
        OrganizationNotFoundError: If org not found
    """
    result = await db.execute(
        select(Organization).where(
            Organization.slug == slug,
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()

    if not org:
        raise OrganizationNotFoundError()

    return OrganizationResponse.model_validate(org)


async def create_organization(
    db: AsyncSession,
    data: OrganizationCreate,
) -> OrganizationResponse:
    """Create a new organization.

    Args:
        db: Database session
        data: Organization creation data

    Raises:
        SlugExistsError: If slug already exists
    """
    # Generate or validate slug
    slug = data.slug or _generate_slug(data.name)

    # Check slug uniqueness
    existing = await db.execute(
        select(Organization).where(Organization.slug == slug)
    )
    if existing.scalar_one_or_none():
        raise SlugExistsError()

    org = Organization(
        name=data.name,
        slug=slug,
        description=data.description,
        is_active=True,
        tier="free",
        settings={},
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)

    logger.info(
        "Organization created",
        org_id=str(org.id),
        slug=org.slug,
    )

    return OrganizationResponse.model_validate(org)


async def update_organization(
    db: AsyncSession,
    org_id: str,
    data: OrganizationUpdate,
) -> OrganizationResponse:
    """Update organization details.

    Raises:
        OrganizationNotFoundError: If org not found
    """
    result = await db.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()

    if not org:
        raise OrganizationNotFoundError()

    if data.name is not None:
        org.name = data.name
    if data.description is not None:
        org.description = data.description
    if data.domain is not None:
        org.domain = data.domain
    if data.logo_url is not None:
        org.logo_url = data.logo_url
    if data.settings is not None:
        org.settings = data.settings

    await db.commit()

    logger.info("Organization updated", org_id=org_id)

    return OrganizationResponse.model_validate(org)


async def get_organization_stats(
    db: AsyncSession,
    org_id: str,
) -> OrganizationStatsResponse:
    """Get organization statistics.

    Raises:
        OrganizationNotFoundError: If org not found
    """
    result = await db.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()

    if not org:
        raise OrganizationNotFoundError()

    # Count users
    user_count_result = await db.execute(
        select(func.count()).where(
            User.org_id == org_id,
            User.deleted_at.is_(None),
            User.is_active == True,
        )
    )
    user_count = user_count_result.scalar() or 0

    # Count API keys
    api_key_count_result = await db.execute(
        select(func.count()).where(
            ApiKey.org_id == org_id,
            ApiKey.is_active == True,
            ApiKey.revoked_at.is_(None),
        )
    )
    api_key_count = api_key_count_result.scalar() or 0

    return OrganizationStatsResponse(
        org_id=org_id,
        user_count=user_count,
        api_key_count=api_key_count,
        tier=org.tier,
        is_active=org.is_active,
    )

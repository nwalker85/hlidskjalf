"""Organization management API routes."""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession, RequireAuth, RequireTenant
from app.authz.client import check_permission
from app.core.logging import get_logger
from app.schemas.organizations import (
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationStatsResponse,
    OrganizationUpdate,
)
from app.services.organizations_service import (
    OrganizationError,
    OrganizationNotFoundError,
    SlugExistsError,
    create_organization,
    get_organization,
    get_organization_by_slug,
    get_organization_stats,
    list_organizations,
    update_organization,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])
logger = get_logger(__name__)


def _handle_org_error(error: OrganizationError) -> HTTPException:
    """Convert organization errors to HTTP exceptions."""
    status_map = {
        "org_not_found": status.HTTP_404_NOT_FOUND,
        "slug_exists": status.HTTP_409_CONFLICT,
    }
    return HTTPException(
        status_code=status_map.get(error.code, status.HTTP_400_BAD_REQUEST),
        detail={"error": error.code, "message": error.message},
    )


@router.get("", response_model=OrganizationListResponse)
async def list_orgs(
    db: DbSession,
    user: RequireAuth,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    is_active: bool | None = None,
) -> OrganizationListResponse:
    """List all organizations.

    This is a platform admin endpoint for managing all organizations.
    Regular users should use /organizations/current.
    """
    # TODO: Check if user is platform admin
    # For now, any authenticated user can list orgs
    return await list_organizations(
        db,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
    )


@router.get("/current", response_model=OrganizationResponse)
async def get_current_org(
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> OrganizationResponse:
    """Get the current organization.

    Returns the organization for the current tenant context.
    """
    try:
        return await get_organization(db, tenant.org_id)
    except OrganizationError as e:
        raise _handle_org_error(e)


@router.get("/current/stats", response_model=OrganizationStatsResponse)
async def get_current_org_stats(
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> OrganizationStatsResponse:
    """Get statistics for the current organization.

    Returns user count, API key count, tier, and status.
    """
    try:
        return await get_organization_stats(db, tenant.org_id)
    except OrganizationError as e:
        raise _handle_org_error(e)


@router.patch("/current", response_model=OrganizationResponse)
async def update_current_org(
    data: OrganizationUpdate,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> OrganizationResponse:
    """Update the current organization.

    Requires admin access to the organization.
    """
    # Check permission
    allowed = await check_permission(
        user.user_id, "admin", "organization", tenant.org_id
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "permission_denied", "message": "Only admins can update the organization"},
        )

    try:
        result = await update_organization(db, tenant.org_id, data)
        logger.info(
            "Organization updated via API",
            org_id=tenant.org_id,
            updated_by=user.user_id,
        )
        return result
    except OrganizationError as e:
        raise _handle_org_error(e)


@router.get("/by-slug/{slug}", response_model=OrganizationResponse)
async def get_org_by_slug(
    slug: str,
    db: DbSession,
    user: RequireAuth,
) -> OrganizationResponse:
    """Get an organization by its slug.

    Used for org resolution in multi-tenant routing.
    """
    try:
        return await get_organization_by_slug(db, slug)
    except OrganizationError as e:
        raise _handle_org_error(e)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_org(
    org_id: str,
    db: DbSession,
    user: RequireAuth,
) -> OrganizationResponse:
    """Get an organization by ID.

    Platform admin endpoint.
    """
    try:
        return await get_organization(db, org_id)
    except OrganizationError as e:
        raise _handle_org_error(e)


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    data: OrganizationCreate,
    db: DbSession,
    user: RequireAuth,
) -> OrganizationResponse:
    """Create a new organization.

    Platform admin endpoint for creating new organizations.
    """
    # TODO: Check if user is platform admin
    try:
        result = await create_organization(db, data)
        logger.info(
            "Organization created via API",
            org_id=result.id,
            created_by=user.user_id,
        )
        return result
    except OrganizationError as e:
        raise _handle_org_error(e)


@router.get("/{org_id}/stats", response_model=OrganizationStatsResponse)
async def get_org_stats(
    org_id: str,
    db: DbSession,
    user: RequireAuth,
) -> OrganizationStatsResponse:
    """Get organization statistics.

    Platform admin endpoint.
    """
    try:
        return await get_organization_stats(db, org_id)
    except OrganizationError as e:
        raise _handle_org_error(e)

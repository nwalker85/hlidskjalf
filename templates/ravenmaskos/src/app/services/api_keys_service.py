"""API Key management business logic service."""

import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.tenant import ApiKey
from app.schemas.api_keys import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyRevokeResponse,
    ApiKeyUpdate,
)

logger = get_logger(__name__)
ph = PasswordHasher()


class ApiKeyError(Exception):
    """Base API key error."""

    def __init__(self, message: str, code: str = "api_key_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class ApiKeyNotFoundError(ApiKeyError):
    """API key not found."""

    def __init__(self):
        super().__init__("API key not found", "api_key_not_found")


class ApiKeyRevokedError(ApiKeyError):
    """API key already revoked."""

    def __init__(self):
        super().__init__("API key has already been revoked", "api_key_revoked")


def _generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, prefix, hash)
    """
    # Generate 32-byte key (256 bits of entropy)
    raw_key = secrets.token_urlsafe(32)
    # Prefix for easy identification (first 8 chars)
    prefix = raw_key[:8]
    # Full key with prefix for display
    full_key = f"rmk_{raw_key}"
    # Hash for storage
    key_hash = ph.hash(raw_key)
    return full_key, prefix, key_hash


async def list_api_keys(
    db: AsyncSession,
    org_id: str,
    page: int = 1,
    page_size: int = 20,
    include_revoked: bool = False,
) -> ApiKeyListResponse:
    """List API keys for an organization.

    Args:
        db: Database session
        org_id: Organization ID
        page: Page number (1-indexed)
        page_size: Number of keys per page
        include_revoked: Include revoked keys in results

    Returns:
        Paginated list of API keys
    """
    query = select(ApiKey).where(ApiKey.org_id == org_id)

    if not include_revoked:
        query = query.where(ApiKey.revoked_at.is_(None))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(ApiKey.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    keys = result.scalars().all()

    return ApiKeyListResponse(
        api_keys=[ApiKeyResponse.model_validate(k) for k in keys],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(keys)) < total,
    )


async def get_api_key(
    db: AsyncSession,
    org_id: str,
    key_id: str,
) -> ApiKeyResponse:
    """Get a specific API key by ID.

    Raises:
        ApiKeyNotFoundError: If key not found
    """
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.org_id == org_id,
        )
    )
    key = result.scalar_one_or_none()

    if not key:
        raise ApiKeyNotFoundError()

    return ApiKeyResponse.model_validate(key)


async def create_api_key(
    db: AsyncSession,
    org_id: str,
    data: ApiKeyCreate,
    created_by: str,
) -> ApiKeyCreatedResponse:
    """Create a new API key.

    Args:
        db: Database session
        org_id: Organization ID
        data: Key creation data
        created_by: ID of user creating the key

    Returns:
        Created key response (includes the raw key once)
    """
    # Generate key
    full_key, prefix, key_hash = _generate_api_key()

    # Calculate expiration
    expires_at = None
    if data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)

    # Create API key record
    api_key = ApiKey(
        org_id=org_id,
        name=data.name,
        description=data.description,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=data.scopes,
        is_active=True,
        expires_at=expires_at,
        allowed_ips=data.allowed_ips,
        created_by=created_by,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    logger.info(
        "API key created",
        key_id=str(api_key.id),
        org_id=org_id,
        created_by=created_by,
        prefix=prefix,
    )

    # Return with the actual key (only time it's exposed)
    response = ApiKeyCreatedResponse.model_validate(api_key)
    response.key = full_key
    return response


async def update_api_key(
    db: AsyncSession,
    org_id: str,
    key_id: str,
    data: ApiKeyUpdate,
    updated_by: str,
) -> ApiKeyResponse:
    """Update API key details.

    Raises:
        ApiKeyNotFoundError: If key not found
        ApiKeyRevokedError: If key is revoked
    """
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.org_id == org_id,
        )
    )
    key = result.scalar_one_or_none()

    if not key:
        raise ApiKeyNotFoundError()

    if key.revoked_at:
        raise ApiKeyRevokedError()

    # Update fields
    if data.name is not None:
        key.name = data.name
    if data.description is not None:
        key.description = data.description
    if data.scopes is not None:
        key.scopes = data.scopes
    if data.is_active is not None:
        key.is_active = data.is_active
    if data.allowed_ips is not None:
        key.allowed_ips = data.allowed_ips

    await db.commit()

    logger.info(
        "API key updated",
        key_id=key_id,
        updated_by=updated_by,
    )

    return ApiKeyResponse.model_validate(key)


async def revoke_api_key(
    db: AsyncSession,
    org_id: str,
    key_id: str,
    revoked_by: str,
) -> ApiKeyRevokeResponse:
    """Revoke an API key.

    Raises:
        ApiKeyNotFoundError: If key not found
        ApiKeyRevokedError: If key already revoked
    """
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.org_id == org_id,
        )
    )
    key = result.scalar_one_or_none()

    if not key:
        raise ApiKeyNotFoundError()

    if key.revoked_at:
        raise ApiKeyRevokedError()

    key.revoked_at = datetime.now(timezone.utc)
    key.is_active = False
    await db.commit()

    logger.info(
        "API key revoked",
        key_id=key_id,
        revoked_by=revoked_by,
    )

    return ApiKeyRevokeResponse(
        id=str(key.id),
        revoked_at=key.revoked_at,
    )


async def verify_api_key(
    db: AsyncSession,
    key_prefix: str,
    raw_key: str,
) -> ApiKey | None:
    """Verify an API key and return the key record if valid.

    Args:
        db: Database session
        key_prefix: First 8 characters of the key
        raw_key: The raw key without prefix

    Returns:
        ApiKey if valid, None otherwise
    """
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == key_prefix,
            ApiKey.is_active == True,
            ApiKey.revoked_at.is_(None),
        )
    )
    key = result.scalar_one_or_none()

    if not key:
        return None

    # Verify hash
    try:
        ph.verify(key.key_hash, raw_key)
    except Exception:
        return None

    # Check expiration
    if key.expires_at and datetime.now(timezone.utc) > key.expires_at:
        return None

    # Update usage stats
    key.last_used_at = datetime.now(timezone.utc)
    key.usage_count += 1
    await db.commit()

    return key

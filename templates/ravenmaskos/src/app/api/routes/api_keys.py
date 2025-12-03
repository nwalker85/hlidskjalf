"""API Key management API routes."""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession, RequireAuth, RequireTenant
from app.authz.client import check_permission
from app.core.logging import get_logger
from app.schemas.api_keys import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyRevokeResponse,
    ApiKeyUpdate,
)
from app.services.api_keys_service import (
    ApiKeyError,
    ApiKeyNotFoundError,
    ApiKeyRevokedError,
    create_api_key,
    get_api_key,
    list_api_keys,
    revoke_api_key,
    update_api_key,
)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])
logger = get_logger(__name__)


def _handle_api_key_error(error: ApiKeyError) -> HTTPException:
    """Convert API key errors to HTTP exceptions."""
    status_map = {
        "api_key_not_found": status.HTTP_404_NOT_FOUND,
        "api_key_revoked": status.HTTP_400_BAD_REQUEST,
    }
    return HTTPException(
        status_code=status_map.get(error.code, status.HTTP_400_BAD_REQUEST),
        detail={"error": error.code, "message": error.message},
    )


async def _require_permission(
    user_id: str,
    relation: str,
    object_type: str,
    object_id: str,
    message: str = "Permission denied",
) -> None:
    """Check permission and raise if not allowed."""
    allowed = await check_permission(user_id, relation, object_type, object_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "permission_denied", "message": message},
        )


@router.get("", response_model=ApiKeyListResponse)
async def list_org_api_keys(
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_revoked: bool = Query(False),
) -> ApiKeyListResponse:
    """List API keys for the current organization.

    Members can view API keys, but only admins can manage them.
    """
    await _require_permission(
        user.user_id,
        "member",
        "organization",
        tenant.org_id,
        "Cannot view API keys in this organization",
    )

    return await list_api_keys(
        db,
        tenant.org_id,
        page=page,
        page_size=page_size,
        include_revoked=include_revoked,
    )


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_org_api_key(
    key_id: str,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> ApiKeyResponse:
    """Get a specific API key by ID.

    Requires member access to the organization.
    """
    await _require_permission(
        user.user_id,
        "member",
        "organization",
        tenant.org_id,
        "Cannot view API keys in this organization",
    )

    try:
        return await get_api_key(db, tenant.org_id, key_id)
    except ApiKeyError as e:
        raise _handle_api_key_error(e)


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_org_api_key(
    data: ApiKeyCreate,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> ApiKeyCreatedResponse:
    """Create a new API key.

    Requires admin access. The full key is only returned once - store it securely!
    """
    await _require_permission(
        user.user_id,
        "admin",
        "organization",
        tenant.org_id,
        "Only admins can create API keys",
    )

    result = await create_api_key(db, tenant.org_id, data, user.user_id)
    logger.info(
        "API key created via API",
        key_id=result.id,
        created_by=user.user_id,
    )
    return result


@router.patch("/{key_id}", response_model=ApiKeyResponse)
async def update_org_api_key(
    key_id: str,
    data: ApiKeyUpdate,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> ApiKeyResponse:
    """Update API key details.

    Requires admin access. Cannot update revoked keys.
    """
    await _require_permission(
        user.user_id,
        "admin",
        "organization",
        tenant.org_id,
        "Only admins can update API keys",
    )

    try:
        return await update_api_key(db, tenant.org_id, key_id, data, user.user_id)
    except ApiKeyError as e:
        raise _handle_api_key_error(e)


@router.post("/{key_id}/revoke", response_model=ApiKeyRevokeResponse)
async def revoke_org_api_key(
    key_id: str,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> ApiKeyRevokeResponse:
    """Revoke an API key.

    Requires admin access. Once revoked, the key cannot be used or restored.
    """
    await _require_permission(
        user.user_id,
        "admin",
        "organization",
        tenant.org_id,
        "Only admins can revoke API keys",
    )

    try:
        result = await revoke_api_key(db, tenant.org_id, key_id, user.user_id)
        logger.info(
            "API key revoked via API",
            key_id=key_id,
            revoked_by=user.user_id,
        )
        return result
    except ApiKeyError as e:
        raise _handle_api_key_error(e)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_api_key(
    key_id: str,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> None:
    """Delete an API key (alias for revoke).

    Requires admin access.
    """
    await _require_permission(
        user.user_id,
        "admin",
        "organization",
        tenant.org_id,
        "Only admins can delete API keys",
    )

    try:
        await revoke_api_key(db, tenant.org_id, key_id, user.user_id)
    except ApiKeyError as e:
        raise _handle_api_key_error(e)

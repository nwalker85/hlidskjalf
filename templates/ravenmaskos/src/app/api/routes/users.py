"""User management API routes."""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DbSession, RequireAuth, RequireTenant
from app.authz.client import check_permission
from app.core.logging import get_logger
from app.schemas.users import (
    UserBulkActionRequest,
    UserBulkActionResponse,
    UserCreate,
    UserInviteRequest,
    UserInviteResponse,
    UserListResponse,
    UserPasswordUpdate,
    UserResponse,
    UserRoleUpdate,
    UserUpdate,
)
from app.services.users_service import (
    LastAdminError,
    PermissionDeniedError,
    UserEmailExistsError,
    UserError,
    UserNotFoundError,
    bulk_action,
    create_user,
    delete_user,
    get_user,
    invite_user,
    list_users,
    update_user,
    update_user_roles,
)

router = APIRouter(prefix="/users", tags=["users"])
logger = get_logger(__name__)


def _handle_user_error(error: UserError) -> HTTPException:
    """Convert user errors to HTTP exceptions."""
    status_map = {
        "user_not_found": status.HTTP_404_NOT_FOUND,
        "email_exists": status.HTTP_409_CONFLICT,
        "permission_denied": status.HTTP_403_FORBIDDEN,
        "last_admin": status.HTTP_400_BAD_REQUEST,
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


@router.get("", response_model=UserListResponse)
async def list_org_users(
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    is_active: bool | None = None,
) -> UserListResponse:
    """List users in the current organization.

    Returns a paginated list of users. Requires 'member' access to the
    organization or above.
    """
    # Check permission (member can view users)
    await _require_permission(
        user.user_id,
        "member",
        "organization",
        tenant.org_id,
        "Cannot list users in this organization",
    )

    return await list_users(
        db,
        tenant.org_id,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_org_user(
    user_id: str,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> UserResponse:
    """Get a specific user by ID.

    Requires 'member' access to the organization.
    """
    await _require_permission(
        user.user_id,
        "member",
        "organization",
        tenant.org_id,
        "Cannot view users in this organization",
    )

    try:
        return await get_user(db, tenant.org_id, user_id)
    except UserError as e:
        raise _handle_user_error(e)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_org_user(
    data: UserCreate,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> UserResponse:
    """Create a new user in the organization.

    Requires 'admin' access to the organization.
    """
    await _require_permission(
        user.user_id,
        "admin",
        "organization",
        tenant.org_id,
        "Only admins can create users",
    )

    try:
        result = await create_user(db, tenant.org_id, data, user.user_id)
        logger.info(
            "User created via API",
            new_user_id=result.id,
            created_by=user.user_id,
        )
        return result
    except UserError as e:
        raise _handle_user_error(e)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_org_user(
    user_id: str,
    data: UserUpdate,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> UserResponse:
    """Update user details.

    Requires 'admin' access to the organization, or users can update
    their own non-sensitive fields.
    """
    # Check if user is updating themselves or is admin
    is_self = user_id == user.user_id
    is_admin = await check_permission(
        user.user_id, "admin", "organization", tenant.org_id
    )

    if not is_self and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "permission_denied", "message": "Cannot update other users"},
        )

    # Non-admins can only update limited fields
    if is_self and not is_admin:
        # Only allow updating profile fields
        if data.is_active is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "permission_denied", "message": "Cannot change active status"},
            )

    try:
        return await update_user(db, tenant.org_id, user_id, data, user.user_id)
    except UserError as e:
        raise _handle_user_error(e)


@router.put("/{user_id}/roles", response_model=UserResponse)
async def update_org_user_roles(
    user_id: str,
    data: UserRoleUpdate,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> UserResponse:
    """Update user roles.

    Requires 'admin' access to the organization. Users cannot change
    their own roles.
    """
    await _require_permission(
        user.user_id,
        "admin",
        "organization",
        tenant.org_id,
        "Only admins can modify roles",
    )

    # Prevent self-demotion (could be dangerous)
    if user_id == user.user_id and "admin" not in data.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "self_demotion", "message": "Cannot remove your own admin role"},
        )

    try:
        return await update_user_roles(db, tenant.org_id, user_id, data, user.user_id)
    except UserError as e:
        raise _handle_user_error(e)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_user(
    user_id: str,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> None:
    """Delete a user from the organization.

    Requires 'admin' access. Users cannot delete themselves.
    """
    await _require_permission(
        user.user_id,
        "admin",
        "organization",
        tenant.org_id,
        "Only admins can delete users",
    )

    # Prevent self-deletion
    if user_id == user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "self_deletion", "message": "Cannot delete yourself"},
        )

    try:
        await delete_user(db, tenant.org_id, user_id, user.user_id)
    except UserError as e:
        raise _handle_user_error(e)


@router.post("/invite", response_model=UserInviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_org_user(
    data: UserInviteRequest,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> UserInviteResponse:
    """Invite a user to the organization.

    Sends an invitation email (or returns invite token if send_email=false).
    Requires 'admin' access to the organization.
    """
    await _require_permission(
        user.user_id,
        "admin",
        "organization",
        tenant.org_id,
        "Only admins can invite users",
    )

    try:
        return await invite_user(db, tenant.org_id, data, user.user_id)
    except UserError as e:
        raise _handle_user_error(e)


@router.post("/bulk", response_model=UserBulkActionResponse)
async def bulk_user_action(
    data: UserBulkActionRequest,
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> UserBulkActionResponse:
    """Perform bulk actions on users.

    Supported actions: activate, deactivate, delete.
    Requires 'admin' access to the organization.
    """
    await _require_permission(
        user.user_id,
        "admin",
        "organization",
        tenant.org_id,
        "Only admins can perform bulk actions",
    )

    # Prevent self-action
    if user.user_id in data.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "self_action", "message": "Cannot perform bulk action on yourself"},
        )

    success_count, failed_count, failed_ids = await bulk_action(
        db, tenant.org_id, data.user_ids, data.action, user.user_id
    )

    return UserBulkActionResponse(
        success_count=success_count,
        failed_count=failed_count,
        failed_ids=failed_ids,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    db: DbSession,
    user: RequireAuth,
    tenant: RequireTenant,
) -> UserResponse:
    """Get the current user's profile.

    This is a convenience endpoint that returns the authenticated
    user's full profile information.
    """
    try:
        return await get_user(db, tenant.org_id, user.user_id)
    except UserError as e:
        raise _handle_user_error(e)

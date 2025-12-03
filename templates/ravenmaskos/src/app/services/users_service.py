"""User management business logic service."""

import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.client import check_permission, delete_relationship, write_relationship
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.tenant import User
from app.schemas.users import (
    UserCreate,
    UserInviteRequest,
    UserInviteResponse,
    UserListResponse,
    UserResponse,
    UserRoleUpdate,
    UserUpdate,
)

logger = get_logger(__name__)


class UserError(Exception):
    """Base user management error."""

    def __init__(self, message: str, code: str = "user_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class UserNotFoundError(UserError):
    """User not found."""

    def __init__(self):
        super().__init__("User not found", "user_not_found")


class UserEmailExistsError(UserError):
    """Email already exists in organization."""

    def __init__(self):
        super().__init__("Email already exists in this organization", "email_exists")


class PermissionDeniedError(UserError):
    """Permission denied for this operation."""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, "permission_denied")


class LastAdminError(UserError):
    """Cannot remove the last admin."""

    def __init__(self):
        super().__init__("Cannot remove the last admin from the organization", "last_admin")


async def list_users(
    db: AsyncSession,
    org_id: str,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    is_active: bool | None = None,
) -> UserListResponse:
    """List users in an organization.

    Args:
        db: Database session
        org_id: Organization ID to list users for
        page: Page number (1-indexed)
        page_size: Number of users per page
        search: Optional search term for email/name
        is_active: Optional filter for active status

    Returns:
        Paginated list of users
    """
    query = select(User).where(User.org_id == org_id, User.deleted_at.is_(None))

    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.email.ilike(search_term)) | (User.full_name.ilike(search_term))
        )

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(users)) < total,
    )


async def get_user(
    db: AsyncSession,
    org_id: str,
    user_id: str,
) -> UserResponse:
    """Get a specific user by ID.

    Raises:
        UserNotFoundError: If user not found
    """
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.org_id == org_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise UserNotFoundError()

    return UserResponse.model_validate(user)


async def create_user(
    db: AsyncSession,
    org_id: str,
    data: UserCreate,
    created_by: str,
) -> UserResponse:
    """Create a new user in the organization.

    Args:
        db: Database session
        org_id: Organization ID
        data: User creation data
        created_by: ID of user creating this user

    Raises:
        UserEmailExistsError: If email already exists
    """
    # Check if email exists in org
    existing = await db.execute(
        select(User).where(
            User.org_id == org_id,
            User.email.ilike(data.email),
            User.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise UserEmailExistsError()

    # Create user
    user = User(
        org_id=org_id,
        email=data.email.lower(),
        full_name=data.full_name,
        username=data.username,
        password_hash=hash_password(data.password),
        is_active=True,
        is_verified=False,
        roles=data.roles,
        scopes=_get_scopes_for_roles(data.roles),
    )
    db.add(user)
    await db.flush()

    # Write OpenFGA relationships based on roles
    await _sync_openfga_roles(str(user.id), org_id, data.roles)

    await db.commit()

    logger.info(
        "User created",
        user_id=str(user.id),
        org_id=org_id,
        email=data.email,
        created_by=created_by,
    )

    return UserResponse.model_validate(user)


async def update_user(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    data: UserUpdate,
    updated_by: str,
) -> UserResponse:
    """Update user details.

    Raises:
        UserNotFoundError: If user not found
    """
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.org_id == org_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise UserNotFoundError()

    # Update fields
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.username is not None:
        user.username = data.username
    if data.avatar_url is not None:
        user.avatar_url = data.avatar_url
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.preferences is not None:
        user.preferences = data.preferences

    await db.commit()

    logger.info(
        "User updated",
        user_id=user_id,
        updated_by=updated_by,
    )

    return UserResponse.model_validate(user)


async def update_user_roles(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    data: UserRoleUpdate,
    updated_by: str,
) -> UserResponse:
    """Update user roles.

    Raises:
        UserNotFoundError: If user not found
        LastAdminError: If trying to remove last admin
    """
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.org_id == org_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise UserNotFoundError()

    # Check if removing admin role
    was_admin = "admin" in user.roles
    will_be_admin = "admin" in data.roles

    if was_admin and not will_be_admin:
        # Check if this is the last admin
        admin_count = await db.execute(
            select(func.count()).where(
                User.org_id == org_id,
                User.roles.contains(["admin"]),
                User.is_active == True,
                User.deleted_at.is_(None),
            )
        )
        if admin_count.scalar() <= 1:
            raise LastAdminError()

    old_roles = user.roles.copy()
    user.roles = data.roles
    user.scopes = _get_scopes_for_roles(data.roles)

    # Sync OpenFGA relationships
    await _sync_openfga_roles(user_id, org_id, data.roles, old_roles)

    await db.commit()

    logger.info(
        "User roles updated",
        user_id=user_id,
        old_roles=old_roles,
        new_roles=data.roles,
        updated_by=updated_by,
    )

    return UserResponse.model_validate(user)


async def delete_user(
    db: AsyncSession,
    org_id: str,
    user_id: str,
    deleted_by: str,
) -> None:
    """Soft delete a user.

    Raises:
        UserNotFoundError: If user not found
        LastAdminError: If trying to delete last admin
    """
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.org_id == org_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise UserNotFoundError()

    # Check if this is the last admin
    if "admin" in user.roles:
        admin_count = await db.execute(
            select(func.count()).where(
                User.org_id == org_id,
                User.roles.contains(["admin"]),
                User.is_active == True,
                User.deleted_at.is_(None),
            )
        )
        if admin_count.scalar() <= 1:
            raise LastAdminError()

    # Soft delete
    user.deleted_at = datetime.now(timezone.utc)
    user.is_active = False

    # Remove all OpenFGA relationships
    for role in user.roles:
        openfga_relation = _role_to_openfga_relation(role)
        if openfga_relation:
            await delete_relationship(user_id, openfga_relation, "organization", org_id)

    await db.commit()

    logger.info(
        "User deleted",
        user_id=user_id,
        deleted_by=deleted_by,
    )


async def invite_user(
    db: AsyncSession,
    org_id: str,
    data: UserInviteRequest,
    invited_by: str,
) -> UserInviteResponse:
    """Invite a user to the organization.

    Creates a user record with a pending status and generates an invite token.

    Raises:
        UserEmailExistsError: If email already exists
    """
    # Check if email exists
    existing = await db.execute(
        select(User).where(
            User.org_id == org_id,
            User.email.ilike(data.email),
            User.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise UserEmailExistsError()

    # Generate invite token
    invite_token = secrets.token_urlsafe(32)

    # Create user with pending verification
    user = User(
        org_id=org_id,
        email=data.email.lower(),
        full_name=data.full_name,
        is_active=False,  # Inactive until invite accepted
        is_verified=False,
        roles=data.roles,
        scopes=_get_scopes_for_roles(data.roles),
        # Store invite token in preferences (would be separate table in production)
        preferences={"invite_token": invite_token, "invited_by": invited_by},
    )
    db.add(user)
    await db.commit()

    logger.info(
        "User invited",
        user_id=str(user.id),
        email=data.email,
        invited_by=invited_by,
    )

    # TODO: Send invite email if data.send_email is True

    return UserInviteResponse(
        user_id=str(user.id),
        email=data.email,
        invite_token=invite_token if not data.send_email else None,
    )


async def bulk_action(
    db: AsyncSession,
    org_id: str,
    user_ids: list[str],
    action: str,
    performed_by: str,
) -> tuple[int, int, list[str]]:
    """Perform bulk action on users.

    Returns:
        Tuple of (success_count, failed_count, failed_ids)
    """
    success_count = 0
    failed_count = 0
    failed_ids = []

    for user_id in user_ids:
        try:
            if action == "activate":
                await _activate_user(db, org_id, user_id)
            elif action == "deactivate":
                await _deactivate_user(db, org_id, user_id)
            elif action == "delete":
                await delete_user(db, org_id, user_id, performed_by)
            success_count += 1
        except Exception as e:
            logger.warning(
                "Bulk action failed for user",
                user_id=user_id,
                action=action,
                error=str(e),
            )
            failed_count += 1
            failed_ids.append(user_id)

    await db.commit()

    logger.info(
        "Bulk action completed",
        action=action,
        success_count=success_count,
        failed_count=failed_count,
        performed_by=performed_by,
    )

    return success_count, failed_count, failed_ids


async def _activate_user(db: AsyncSession, org_id: str, user_id: str) -> None:
    """Activate a user."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.org_id == org_id)
    )
    user = result.scalar_one_or_none()
    if user:
        user.is_active = True


async def _deactivate_user(db: AsyncSession, org_id: str, user_id: str) -> None:
    """Deactivate a user."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.org_id == org_id)
    )
    user = result.scalar_one_or_none()
    if user:
        # Check if last admin
        if "admin" in user.roles:
            admin_count = await db.execute(
                select(func.count()).where(
                    User.org_id == org_id,
                    User.roles.contains(["admin"]),
                    User.is_active == True,
                    User.deleted_at.is_(None),
                )
            )
            if admin_count.scalar() <= 1:
                raise LastAdminError()
        user.is_active = False


def _get_scopes_for_roles(roles: list[str]) -> list[str]:
    """Get scopes based on roles."""
    scopes = []

    if "admin" in roles:
        scopes = ["org:*", "users:*", "roles:*", "api-keys:*", "audit:read"]
    elif "member" in roles:
        scopes = ["org:read", "users:read", "api-keys:read"]
    elif "viewer" in roles:
        scopes = ["org:read"]

    return scopes


def _role_to_openfga_relation(role: str) -> str | None:
    """Map role name to OpenFGA relation."""
    mapping = {
        "admin": "admin",
        "member": "member",
        "viewer": "viewer",
    }
    return mapping.get(role)


async def _sync_openfga_roles(
    user_id: str,
    org_id: str,
    new_roles: list[str],
    old_roles: list[str] | None = None,
) -> None:
    """Sync user roles with OpenFGA.

    Args:
        user_id: User ID
        org_id: Organization ID
        new_roles: New role list
        old_roles: Previous role list (for updates)
    """
    old_roles = old_roles or []

    # Remove old relations not in new roles
    for role in old_roles:
        if role not in new_roles:
            relation = _role_to_openfga_relation(role)
            if relation:
                await delete_relationship(user_id, relation, "organization", org_id)

    # Add new relations
    for role in new_roles:
        if role not in old_roles:
            relation = _role_to_openfga_relation(role)
            if relation:
                await write_relationship(user_id, relation, "organization", org_id)

"""Authentication business logic service."""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    check_needs_rehash,
)
from app.models.tenant import Organization, User
from app.schemas.auth import (
    CurrentUserResponse,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)

logger = get_logger(__name__)


class AuthError(Exception):
    """Base authentication error."""

    def __init__(self, message: str, code: str = "auth_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class InvalidCredentialsError(AuthError):
    """Invalid email or password."""

    def __init__(self):
        super().__init__("Invalid email or password", "invalid_credentials")


class UserNotFoundError(AuthError):
    """User not found."""

    def __init__(self):
        super().__init__("User not found", "user_not_found")


class UserInactiveError(AuthError):
    """User account is inactive."""

    def __init__(self):
        super().__init__("Account is inactive", "user_inactive")


class UserLockedError(AuthError):
    """User account is locked."""

    def __init__(self, until: datetime | None = None):
        if until:
            super().__init__(f"Account is locked until {until.isoformat()}", "user_locked")
        else:
            super().__init__("Account is locked", "user_locked")


class EmailAlreadyExistsError(AuthError):
    """Email already registered."""

    def __init__(self):
        super().__init__("Email already registered", "email_exists")


class InvalidTokenError(AuthError):
    """Invalid or expired token."""

    def __init__(self):
        super().__init__("Invalid or expired token", "invalid_token")


class MFARequiredError(AuthError):
    """MFA verification required."""

    def __init__(self, mfa_token: str):
        super().__init__("MFA verification required", "mfa_required")
        self.mfa_token = mfa_token


def _generate_org_slug(name: str) -> str:
    """Generate URL-safe slug from organization name."""
    import re

    # Lowercase, replace spaces with hyphens, remove special chars
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    # Add random suffix to ensure uniqueness
    suffix = secrets.token_hex(4)
    return f"{slug[:50]}-{suffix}"


async def authenticate_user(
    db: AsyncSession,
    credentials: LoginRequest,
) -> tuple[User, Organization]:
    """Authenticate user with email and password.

    Returns:
        Tuple of (User, Organization) if successful.

    Raises:
        InvalidCredentialsError: If credentials are invalid.
        UserInactiveError: If user is inactive.
        UserLockedError: If user is locked.
    """
    # Find user by email (case insensitive)
    result = await db.execute(
        select(User).where(User.email.ilike(credentials.email)).limit(1)
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.warning("Login attempt for non-existent email", email=credentials.email)
        raise InvalidCredentialsError()

    # Check if account is locked
    if user.is_locked:
        logger.warning("Login attempt for locked account", user_id=str(user.id))
        raise UserLockedError(user.locked_until)

    # Verify password
    if not user.password_hash or not verify_password(credentials.password, user.password_hash):
        # Increment failed login count
        user.failed_login_count += 1

        # Lock account after 5 failed attempts
        if user.failed_login_count >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            logger.warning("Account locked due to failed attempts", user_id=str(user.id))

        await db.commit()
        raise InvalidCredentialsError()

    # Check if account is active
    if not user.is_active:
        raise UserInactiveError()

    # Reset failed login count on success
    if user.failed_login_count > 0:
        user.failed_login_count = 0
        user.locked_until = None

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)

    # Check if password needs rehash
    if check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(credentials.password)
        logger.info("Password rehashed", user_id=str(user.id))

    await db.commit()

    # Load organization
    org_result = await db.execute(
        select(Organization).where(Organization.id == user.org_id)
    )
    org = org_result.scalar_one()

    return user, org


def create_tokens(user: User, org: Organization) -> TokenResponse:
    """Create access and refresh tokens for user."""
    extra_claims = {
        "email": user.email,
        "org_id": str(user.org_id),
        "roles": user.roles,
        "scopes": user.scopes,
    }

    access_token = create_access_token(str(user.id), extra_claims)
    refresh_token = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def refresh_access_token(
    db: AsyncSession,
    refresh_token: str,
) -> TokenResponse:
    """Refresh access token using refresh token.

    Raises:
        InvalidTokenError: If refresh token is invalid or expired.
        UserNotFoundError: If user no longer exists.
        UserInactiveError: If user is inactive.
    """
    # Decode refresh token
    payload = decode_token(refresh_token, expected_type="refresh")
    if not payload:
        raise InvalidTokenError()

    # Load user
    result = await db.execute(select(User).where(User.id == payload.sub))
    user = result.scalar_one_or_none()

    if not user:
        raise UserNotFoundError()

    if not user.is_active:
        raise UserInactiveError()

    # Load organization
    org_result = await db.execute(
        select(Organization).where(Organization.id == user.org_id)
    )
    org = org_result.scalar_one()

    # Create new tokens
    return create_tokens(user, org)


async def register_user(
    db: AsyncSession,
    data: RegisterRequest,
) -> RegisterResponse:
    """Register a new user and optionally create organization.

    Raises:
        EmailAlreadyExistsError: If email is already registered.
    """
    # Check if email exists
    existing = await db.execute(
        select(User).where(User.email.ilike(data.email)).limit(1)
    )
    if existing.scalar_one_or_none():
        raise EmailAlreadyExistsError()

    # Create organization if name provided, otherwise use default
    org_name = data.org_name or f"{data.full_name}'s Organization"
    org_slug = _generate_org_slug(org_name)

    org = Organization(
        name=org_name,
        slug=org_slug,
        is_active=True,
        tier="free",
    )
    db.add(org)
    await db.flush()  # Get org.id

    # Create user
    user = User(
        org_id=str(org.id),
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        is_active=True,
        is_verified=False,  # Requires email verification
        roles=["admin"],  # First user is org admin
        scopes=["org:*", "users:*", "roles:*", "api-keys:*"],  # Full org permissions
    )
    db.add(user)
    await db.commit()

    logger.info(
        "User registered",
        user_id=str(user.id),
        org_id=str(org.id),
        email=data.email,
    )

    return RegisterResponse(
        user_id=str(user.id),
        email=user.email,
        org_id=str(org.id),
        org_slug=org.slug,
    )


async def get_user_by_id(
    db: AsyncSession,
    user_id: str,
) -> User | None:
    """Get user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_current_user_info(
    db: AsyncSession,
    user_id: str,
) -> CurrentUserResponse:
    """Get current user information.

    Raises:
        UserNotFoundError: If user not found.
    """
    user = await get_user_by_id(db, user_id)
    if not user:
        raise UserNotFoundError()

    # Load organization
    org_result = await db.execute(
        select(Organization).where(Organization.id == user.org_id)
    )
    org = org_result.scalar_one_or_none()

    return CurrentUserResponse(
        user_id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        org_id=str(user.org_id),
        org_slug=org.slug if org else None,
        org_name=org.name if org else None,
        roles=user.roles,
        scopes=user.scopes,
        is_verified=user.is_verified,
        mfa_enabled=user.mfa_enabled,
    )


async def initiate_password_reset(
    db: AsyncSession,
    email: str,
) -> str | None:
    """Initiate password reset and return token.

    Returns None if email not found (to prevent email enumeration).
    In production, this would send an email.
    """
    result = await db.execute(
        select(User).where(User.email.ilike(email)).limit(1)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Don't reveal if email exists
        return None

    # Generate reset token (would be stored in DB in production)
    reset_token = secrets.token_urlsafe(32)

    # TODO: Store token in DB with expiration
    # TODO: Send email with reset link

    logger.info("Password reset initiated", user_id=str(user.id))

    return reset_token


async def complete_password_reset(
    db: AsyncSession,
    token: str,
    new_password: str,
) -> None:
    """Complete password reset with token.

    Raises:
        InvalidTokenError: If token is invalid or expired.
    """
    # TODO: Validate token from DB
    # For now, just validate format
    if len(token) < 32:
        raise InvalidTokenError()

    # TODO: Look up user from token and update password
    raise InvalidTokenError()  # Placeholder until token storage implemented


async def verify_email(
    db: AsyncSession,
    token: str,
) -> None:
    """Verify user email with token.

    Raises:
        InvalidTokenError: If token is invalid or expired.
    """
    # TODO: Validate token from DB
    if len(token) < 32:
        raise InvalidTokenError()

    # TODO: Look up user from token and set is_verified = True
    raise InvalidTokenError()  # Placeholder until token storage implemented

"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession, RequireAuth, CurrentUser
from app.core.logging import get_logger
from app.schemas.auth import (
    CurrentUserResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutResponse,
    MFAVerifyRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.services.auth_service import (
    AuthError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    MFARequiredError,
    UserInactiveError,
    UserLockedError,
    UserNotFoundError,
    authenticate_user,
    complete_password_reset,
    create_tokens,
    get_current_user_info,
    initiate_password_reset,
    refresh_access_token,
    register_user,
    verify_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)


def _handle_auth_error(error: AuthError) -> HTTPException:
    """Convert auth errors to HTTP exceptions."""
    status_map = {
        "invalid_credentials": status.HTTP_401_UNAUTHORIZED,
        "user_not_found": status.HTTP_401_UNAUTHORIZED,
        "user_inactive": status.HTTP_403_FORBIDDEN,
        "user_locked": status.HTTP_403_FORBIDDEN,
        "email_exists": status.HTTP_409_CONFLICT,
        "invalid_token": status.HTTP_401_UNAUTHORIZED,
        "mfa_required": status.HTTP_401_UNAUTHORIZED,
    }
    return HTTPException(
        status_code=status_map.get(error.code, status.HTTP_400_BAD_REQUEST),
        detail={"error": error.code, "message": error.message},
    )


@router.post("/token", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: DbSession,
) -> TokenResponse:
    """Authenticate user and return JWT tokens.

    Returns access and refresh tokens. The access token should be used
    in the Authorization header for subsequent requests.
    """
    try:
        user, org = await authenticate_user(db, credentials)

        # Check if MFA is enabled
        if user.mfa_enabled:
            # TODO: Generate MFA session token and return MFA required response
            pass

        return create_tokens(user, org)
    except AuthError as e:
        logger.warning("Login failed", email=credentials.email, error=e.code)
        raise _handle_auth_error(e)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    request: RefreshRequest,
    db: DbSession,
) -> RefreshResponse:
    """Refresh access token using refresh token.

    Use this endpoint when the access token expires to get a new one
    without requiring the user to log in again.
    """
    try:
        tokens = await refresh_access_token(db, request.refresh_token)
        return RefreshResponse(
            access_token=tokens.access_token,
            expires_in=tokens.expires_in,
        )
    except AuthError as e:
        logger.warning("Token refresh failed", error=e.code)
        raise _handle_auth_error(e)


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    user: RequireAuth,
    db: DbSession,
) -> CurrentUserResponse:
    """Get current authenticated user information.

    Returns user profile, organization, roles, and permissions.
    """
    try:
        return await get_current_user_info(db, user.user_id)
    except AuthError as e:
        raise _handle_auth_error(e)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    user: RequireAuth,
) -> LogoutResponse:
    """Logout user and invalidate refresh token.

    Note: This endpoint currently only returns success. In production,
    you would invalidate the refresh token in a blacklist/database.
    """
    logger.info("User logged out", user_id=user.user_id)
    # TODO: Invalidate refresh token in database
    return LogoutResponse()


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    db: DbSession,
) -> RegisterResponse:
    """Register a new user and create organization.

    Creates a new organization with the user as admin. The user will
    need to verify their email before full access is granted.
    """
    try:
        return await register_user(db, data)
    except AuthError as e:
        logger.warning("Registration failed", email=data.email, error=e.code)
        raise _handle_auth_error(e)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: DbSession,
) -> ForgotPasswordResponse:
    """Request password reset email.

    If the email exists, a reset link will be sent. The response is
    always the same to prevent email enumeration.
    """
    token = await initiate_password_reset(db, request.email)
    # Note: In production, send email with token
    if token:
        logger.info("Password reset token generated", email=request.email)
    return ForgotPasswordResponse()


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: DbSession,
) -> ResetPasswordResponse:
    """Reset password using token from email.

    Completes the password reset flow. The token is single-use and
    expires after a set period.
    """
    try:
        await complete_password_reset(db, request.token, request.new_password)
        return ResetPasswordResponse()
    except AuthError as e:
        raise _handle_auth_error(e)


@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email_endpoint(
    request: VerifyEmailRequest,
    db: DbSession,
) -> VerifyEmailResponse:
    """Verify user email using token.

    Completes email verification. The token is single-use and sent
    via email during registration.
    """
    try:
        await verify_email(db, request.token)
        return VerifyEmailResponse()
    except AuthError as e:
        raise _handle_auth_error(e)


@router.post("/mfa/verify", response_model=TokenResponse)
async def verify_mfa(
    request: MFAVerifyRequest,
    db: DbSession,
) -> TokenResponse:
    """Verify MFA code and complete login.

    Used after initial login when MFA is enabled. Provide the
    temporary MFA token and 6-digit code from authenticator app.
    """
    # TODO: Implement MFA verification
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="MFA verification not yet implemented",
    )

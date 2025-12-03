"""Authentication request/response schemas."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Login request with email and password."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Token response after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token expiration in seconds")


class RefreshRequest(BaseModel):
    """Request to refresh access token."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Response after token refresh."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: str = Field(..., min_length=1, max_length=255)
    org_name: str | None = Field(
        None, min_length=1, max_length=255, description="Organization name (creates new org)"
    )


class RegisterResponse(BaseModel):
    """Response after successful registration."""

    user_id: str
    email: str
    org_id: str
    org_slug: str
    message: str = "Registration successful. Please verify your email."


class CurrentUserResponse(BaseModel):
    """Current authenticated user info."""

    user_id: str
    email: str
    full_name: str | None
    org_id: str
    org_slug: str | None = None
    org_name: str | None = None
    roles: list[str]
    scopes: list[str]
    is_verified: bool
    mfa_enabled: bool


class ForgotPasswordRequest(BaseModel):
    """Request to initiate password reset."""

    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Response after password reset request."""

    message: str = "If the email exists, a reset link has been sent."


class ResetPasswordRequest(BaseModel):
    """Request to reset password with token."""

    token: str
    new_password: str = Field(..., min_length=8)


class ResetPasswordResponse(BaseModel):
    """Response after successful password reset."""

    message: str = "Password reset successful."


class VerifyEmailRequest(BaseModel):
    """Request to verify email."""

    token: str


class VerifyEmailResponse(BaseModel):
    """Response after email verification."""

    message: str = "Email verified successfully."
    verified: bool = True


class MFARequiredResponse(BaseModel):
    """Response when MFA is required."""

    mfa_required: bool = True
    mfa_token: str = Field(description="Temporary token for MFA verification")


class MFAVerifyRequest(BaseModel):
    """Request to verify MFA code."""

    mfa_token: str
    code: str = Field(..., min_length=6, max_length=6)


class LogoutResponse(BaseModel):
    """Response after logout."""

    message: str = "Logged out successfully."

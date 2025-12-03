"""User management request/response schemas."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user fields."""

    email: EmailStr
    full_name: str | None = None
    username: str | None = None


class UserCreate(UserBase):
    """Request to create a new user."""

    password: str = Field(..., min_length=8)
    roles: list[str] = Field(default_factory=lambda: ["member"])


class UserUpdate(BaseModel):
    """Request to update a user."""

    full_name: str | None = None
    username: str | None = None
    avatar_url: str | None = None
    is_active: bool | None = None
    preferences: dict | None = None


class UserRoleUpdate(BaseModel):
    """Request to update user roles."""

    roles: list[str] = Field(..., min_length=1)


class UserPasswordUpdate(BaseModel):
    """Request to update user password (admin action)."""

    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """User response model."""

    id: str
    email: str
    username: str | None
    full_name: str | None
    avatar_url: str | None
    is_active: bool
    is_verified: bool
    roles: list[str]
    scopes: list[str]
    mfa_enabled: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Response for user list."""

    users: list[UserResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class UserInviteRequest(BaseModel):
    """Request to invite a user to the organization."""

    email: EmailStr
    full_name: str | None = None
    roles: list[str] = Field(default_factory=lambda: ["member"])
    send_email: bool = True


class UserInviteResponse(BaseModel):
    """Response after user invite."""

    user_id: str
    email: str
    invite_token: str | None = Field(None, description="Token for invite link (if send_email=false)")
    message: str = "Invitation sent successfully"


class UserBulkActionRequest(BaseModel):
    """Request for bulk user actions."""

    user_ids: list[str] = Field(..., min_length=1, max_length=100)
    action: str = Field(..., pattern="^(activate|deactivate|delete)$")


class UserBulkActionResponse(BaseModel):
    """Response for bulk user actions."""

    success_count: int
    failed_count: int
    failed_ids: list[str] = Field(default_factory=list)

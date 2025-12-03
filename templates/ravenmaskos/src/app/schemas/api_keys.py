"""API Key management request/response schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


class ApiKeyBase(BaseModel):
    """Base API key fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    scopes: list[str] = Field(default_factory=list)


class ApiKeyCreate(ApiKeyBase):
    """Request to create a new API key."""

    expires_in_days: int | None = Field(
        None, ge=1, le=365, description="Days until expiration (null = never expires)"
    )
    allowed_ips: list[str] | None = None


class ApiKeyUpdate(BaseModel):
    """Request to update an API key."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    scopes: list[str] | None = None
    is_active: bool | None = None
    allowed_ips: list[str] | None = None


class ApiKeyResponse(BaseModel):
    """API key response model (without the actual key)."""

    id: str
    name: str
    description: str | None
    key_prefix: str = Field(description="First 8 characters of the key for identification")
    scopes: list[str]
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    usage_count: int
    allowed_ips: list[str] | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Response after creating an API key (includes the raw key)."""

    key: str = Field(
        description="The full API key. This is only shown once - store it securely!"
    )


class ApiKeyListResponse(BaseModel):
    """Response for API key list."""

    api_keys: list[ApiKeyResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class ApiKeyRevokeResponse(BaseModel):
    """Response after revoking an API key."""

    id: str
    revoked_at: datetime
    message: str = "API key has been revoked"

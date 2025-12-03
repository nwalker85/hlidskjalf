"""Organization management request/response schemas."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class OrganizationBase(BaseModel):
    """Base organization fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class OrganizationCreate(OrganizationBase):
    """Request to create a new organization."""

    slug: str | None = Field(
        None, min_length=3, max_length=63, pattern="^[a-z0-9-]+$"
    )


class OrganizationUpdate(BaseModel):
    """Request to update an organization."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    domain: str | None = None
    logo_url: str | None = None
    settings: dict | None = None


class OrganizationResponse(BaseModel):
    """Organization response model."""

    id: str
    name: str
    slug: str
    description: str | None
    is_active: bool
    tier: Literal["free", "starter", "professional", "enterprise"]
    domain: str | None
    logo_url: str | None
    settings: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationListResponse(BaseModel):
    """Response for organization list."""

    organizations: list[OrganizationResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class OrganizationStatsResponse(BaseModel):
    """Organization statistics."""

    org_id: str
    user_count: int
    api_key_count: int
    tier: str
    is_active: bool

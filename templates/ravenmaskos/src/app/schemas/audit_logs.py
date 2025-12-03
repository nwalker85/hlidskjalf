"""Audit log query schemas."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    """Audit log entry response model."""

    id: str
    timestamp: datetime
    actor_id: str
    actor_type: Literal["user", "service", "system"]
    actor_email: str | None = None
    action: str
    resource_type: str
    resource_id: str
    org_id: str
    ip_address: str | None = None
    user_agent: str | None = None
    outcome: Literal["success", "failure"]
    details: dict = Field(default_factory=dict)


class AuditLogListResponse(BaseModel):
    """Response for audit log list."""

    logs: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
    has_more: bool


class AuditLogQueryParams(BaseModel):
    """Query parameters for audit log filtering."""

    actor_id: str | None = None
    actor_type: Literal["user", "service", "system"] | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    outcome: Literal["success", "failure"] | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class AuditLogStats(BaseModel):
    """Audit log statistics for the dashboard."""

    total_events: int
    success_count: int
    failure_count: int
    top_actions: list[dict]
    top_actors: list[dict]

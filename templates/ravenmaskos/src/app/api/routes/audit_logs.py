"""Audit log API routes."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import RequireAuth, RequireTenant
from app.authz.client import check_permission
from app.core.logging import get_logger
from app.schemas.audit_logs import (
    AuditLogListResponse,
    AuditLogQueryParams,
    AuditLogStats,
)
from app.services.audit_logs_service import get_audit_stats, query_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])
logger = get_logger(__name__)


async def _require_audit_access(user_id: str, org_id: str) -> None:
    """Check if user has audit log access (admin only)."""
    allowed = await check_permission(user_id, "admin", "organization", org_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "permission_denied", "message": "Only admins can view audit logs"},
        )


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    user: RequireAuth,
    tenant: RequireTenant,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    actor_id: str | None = None,
    actor_type: Literal["user", "service", "system"] | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    outcome: Literal["success", "failure"] | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> AuditLogListResponse:
    """List audit logs for the current organization.

    Requires admin access. Supports filtering by actor, action, resource,
    outcome, and date range.
    """
    await _require_audit_access(user.user_id, tenant.org_id)

    params = AuditLogQueryParams(
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        start_date=start_date,
        end_date=end_date,
    )

    return await query_audit_logs(
        tenant.org_id,
        page=page,
        page_size=page_size,
        params=params,
    )


@router.get("/stats", response_model=AuditLogStats)
async def get_stats(
    user: RequireAuth,
    tenant: RequireTenant,
) -> AuditLogStats:
    """Get audit log statistics for the dashboard.

    Returns total events, success/failure counts, and top actions/actors.
    """
    await _require_audit_access(user.user_id, tenant.org_id)

    return await get_audit_stats(tenant.org_id)

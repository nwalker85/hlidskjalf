"""Audit log query service.

This service provides read access to audit logs. In a production system,
audit logs would be stored in a time-series database or log aggregation
system (e.g., Elasticsearch, ClickHouse) and potentially streamed via Kafka.

For this implementation, we'll use an in-memory mock that demonstrates
the API structure. The actual integration with Kafka would consume events
and store them in a queryable format.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from app.core.logging import get_logger
from app.schemas.audit_logs import (
    AuditLogEntry,
    AuditLogListResponse,
    AuditLogQueryParams,
    AuditLogStats,
)

logger = get_logger(__name__)

# In-memory store for demo purposes
# In production, this would query Elasticsearch/ClickHouse/etc.
_audit_logs: list[dict] = []


def _generate_mock_logs(org_id: str) -> list[dict]:
    """Generate mock audit logs for demo purposes."""
    now = datetime.now(timezone.utc)
    actions = [
        ("user.login", "user", "success"),
        ("user.created", "user", "success"),
        ("user.updated", "user", "success"),
        ("user.deleted", "user", "success"),
        ("api_key.created", "api_key", "success"),
        ("api_key.revoked", "api_key", "success"),
        ("organization.updated", "organization", "success"),
        ("user.login", "user", "failure"),
        ("api_key.used", "api_key", "success"),
        ("role.assigned", "user", "success"),
    ]

    logs = []
    for i in range(50):
        action, resource_type, outcome = actions[i % len(actions)]
        logs.append({
            "id": str(uuid4()),
            "timestamp": now - timedelta(hours=i, minutes=i * 2),
            "actor_id": f"user-{(i % 3) + 1}",
            "actor_type": "user",
            "actor_email": f"user{(i % 3) + 1}@example.com",
            "action": action,
            "resource_type": resource_type,
            "resource_id": f"{resource_type}-{i}",
            "org_id": org_id,
            "ip_address": f"192.168.1.{i % 256}",
            "user_agent": "Mozilla/5.0",
            "outcome": outcome,
            "details": {"note": f"Action {i}"},
        })
    return logs


async def log_audit_event(
    org_id: str,
    actor_id: str,
    actor_type: Literal["user", "service", "system"],
    action: str,
    resource_type: str,
    resource_id: str,
    outcome: Literal["success", "failure"],
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    actor_email: str | None = None,
) -> None:
    """Log an audit event.

    In production, this would publish to Kafka for async processing.
    """
    event = {
        "id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc),
        "actor_id": actor_id,
        "actor_type": actor_type,
        "actor_email": actor_email,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "org_id": org_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "outcome": outcome,
        "details": details or {},
    }

    # In production: await kafka_producer.send("audit-logs", event)
    _audit_logs.append(event)

    logger.info(
        "Audit event logged",
        action=action,
        actor_id=actor_id,
        resource_type=resource_type,
        outcome=outcome,
    )


async def query_audit_logs(
    org_id: str,
    page: int = 1,
    page_size: int = 50,
    params: AuditLogQueryParams | None = None,
) -> AuditLogListResponse:
    """Query audit logs for an organization.

    Args:
        org_id: Organization ID
        page: Page number (1-indexed)
        page_size: Number of logs per page
        params: Optional filter parameters

    Returns:
        Paginated list of audit log entries
    """
    # Get or generate mock logs for this org
    global _audit_logs
    if not _audit_logs:
        _audit_logs = _generate_mock_logs(org_id)

    # Filter by org
    logs = [log for log in _audit_logs if log["org_id"] == org_id]

    # Apply filters
    if params:
        if params.actor_id:
            logs = [log for log in logs if log["actor_id"] == params.actor_id]
        if params.actor_type:
            logs = [log for log in logs if log["actor_type"] == params.actor_type]
        if params.action:
            logs = [log for log in logs if params.action in log["action"]]
        if params.resource_type:
            logs = [log for log in logs if log["resource_type"] == params.resource_type]
        if params.resource_id:
            logs = [log for log in logs if log["resource_id"] == params.resource_id]
        if params.outcome:
            logs = [log for log in logs if log["outcome"] == params.outcome]
        if params.start_date:
            logs = [log for log in logs if log["timestamp"] >= params.start_date]
        if params.end_date:
            logs = [log for log in logs if log["timestamp"] <= params.end_date]

    # Sort by timestamp descending
    logs.sort(key=lambda x: x["timestamp"], reverse=True)

    total = len(logs)
    offset = (page - 1) * page_size
    page_logs = logs[offset : offset + page_size]

    return AuditLogListResponse(
        logs=[AuditLogEntry(**log) for log in page_logs],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(page_logs)) < total,
    )


async def get_audit_stats(org_id: str) -> AuditLogStats:
    """Get audit log statistics for the dashboard.

    Args:
        org_id: Organization ID

    Returns:
        Statistics including counts and top actions/actors
    """
    global _audit_logs
    if not _audit_logs:
        _audit_logs = _generate_mock_logs(org_id)

    logs = [log for log in _audit_logs if log["org_id"] == org_id]

    total = len(logs)
    success_count = sum(1 for log in logs if log["outcome"] == "success")
    failure_count = total - success_count

    # Count actions
    action_counts: dict[str, int] = {}
    for log in logs:
        action_counts[log["action"]] = action_counts.get(log["action"], 0) + 1

    top_actions = sorted(
        [{"action": k, "count": v} for k, v in action_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    # Count actors
    actor_counts: dict[str, int] = {}
    for log in logs:
        actor_counts[log["actor_id"]] = actor_counts.get(log["actor_id"], 0) + 1

    top_actors = sorted(
        [{"actor_id": k, "count": v} for k, v in actor_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    return AuditLogStats(
        total_events=total,
        success_count=success_count,
        failure_count=failure_count,
        top_actions=top_actions,
        top_actors=top_actors,
    )

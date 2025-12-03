"""Audit logging module for compliance and security.

Provides structured audit logging with Kafka sink for
HIPAA, GDPR, and SOC2 compliance requirements.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuditAction(str, Enum):
    """Standard audit action types."""

    # CRUD operations
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGE = "password_change"

    # Authorization
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"

    # API operations
    API_CALL = "api_call"
    RATE_LIMITED = "rate_limited"

    # Agent/AI operations
    AGENT_EXECUTE = "agent_execute"
    TOOL_CALL = "tool_call"
    MCP_CALL = "mcp_call"
    LLM_INFERENCE = "llm_inference"

    # Data operations
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    DATA_ACCESS = "data_access"

    # Administrative
    CONFIG_CHANGE = "config_change"
    SECRET_ACCESS = "secret_access"
    ADMIN_ACTION = "admin_action"


class AuditOutcome(str, Enum):
    """Audit event outcome."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    ERROR = "error"


class ActorType(str, Enum):
    """Type of actor performing the action."""

    USER = "user"
    SERVICE = "service"
    AGENT = "agent"
    SYSTEM = "system"


class AuditEvent(BaseModel):
    """Structured audit event for compliance logging.

    Follows enterprise audit logging standards for HIPAA, GDPR, SOC2.
    """

    # Event identification
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = "audit"

    # Actor information
    actor_id: str
    actor_type: ActorType
    actor_ip: str | None = None
    actor_user_agent: str | None = None

    # Action details
    action: AuditAction
    outcome: AuditOutcome

    # Resource information
    resource_type: str
    resource_id: str | None = None

    # Tenant context
    org_id: str | None = None
    business_unit_id: str | None = None
    environment: str = Field(default_factory=lambda: settings.ENVIRONMENT)

    # Tracing
    trace_id: str | None = None
    span_id: str | None = None
    request_id: str | None = None

    # Additional context
    details: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None

    # Compliance metadata
    data_classification: str | None = None  # public, internal, confidential, restricted
    contains_pii: bool = False
    contains_phi: bool = False

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            Decimal: lambda v: str(v),
        }


class AuditLogger:
    """Audit logger with Kafka sink.

    Provides structured audit logging for compliance requirements.
    Events are published to Kafka for durability and downstream processing.
    """

    AUDIT_TOPIC = "audit.events"

    def __init__(self):
        self._kafka_available = False

    async def _get_kafka(self):
        """Lazy load Kafka to avoid circular imports."""
        try:
            from app.core.kafka import publish

            self._kafka_available = True
            return publish
        except Exception as e:
            logger.warning("Kafka not available for audit logging", error=str(e))
            self._kafka_available = False
            return None

    async def log(self, event: AuditEvent) -> None:
        """Log an audit event.

        Events are:
        1. Logged to structured logger (always)
        2. Published to Kafka topic (if available)
        """
        # Always log to structured logger
        logger.info(
            "Audit event",
            event_id=str(event.event_id),
            action=event.action.value,
            outcome=event.outcome.value,
            actor_id=event.actor_id,
            actor_type=event.actor_type.value,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            org_id=event.org_id,
            trace_id=event.trace_id,
            request_id=event.request_id,
        )

        # Publish to Kafka if available
        publish = await self._get_kafka()
        if publish:
            try:
                await publish(
                    topic=self.AUDIT_TOPIC,
                    value=event.model_dump(mode="json"),
                    key=event.org_id or "system",
                )
            except Exception as e:
                logger.error(
                    "Failed to publish audit event to Kafka",
                    event_id=str(event.event_id),
                    error=str(e),
                )

    async def log_api_call(
        self,
        *,
        actor_id: str,
        actor_type: ActorType,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        org_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        actor_ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log an API call audit event."""
        outcome = AuditOutcome.SUCCESS if status_code < 400 else AuditOutcome.FAILURE
        if status_code == 403:
            outcome = AuditOutcome.DENIED

        event = AuditEvent(
            actor_id=actor_id,
            actor_type=actor_type,
            actor_ip=actor_ip,
            actor_user_agent=user_agent,
            action=AuditAction.API_CALL,
            outcome=outcome,
            resource_type="api_endpoint",
            resource_id=f"{method}:{path}",
            org_id=org_id,
            request_id=request_id,
            trace_id=trace_id,
            details={
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
        await self.log(event)

    async def log_auth_event(
        self,
        *,
        action: AuditAction,
        actor_id: str,
        outcome: AuditOutcome,
        org_id: str | None = None,
        actor_ip: str | None = None,
        user_agent: str | None = None,
        error_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log an authentication event."""
        event = AuditEvent(
            actor_id=actor_id,
            actor_type=ActorType.USER,
            actor_ip=actor_ip,
            actor_user_agent=user_agent,
            action=action,
            outcome=outcome,
            resource_type="authentication",
            org_id=org_id,
            error_message=error_message,
            details=details or {},
        )
        await self.log(event)

    async def log_data_access(
        self,
        *,
        actor_id: str,
        actor_type: ActorType,
        resource_type: str,
        resource_id: str,
        action: AuditAction = AuditAction.DATA_ACCESS,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        org_id: str | None = None,
        contains_pii: bool = False,
        contains_phi: bool = False,
        data_classification: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log a data access event (for compliance)."""
        event = AuditEvent(
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            outcome=outcome,
            resource_type=resource_type,
            resource_id=resource_id,
            org_id=org_id,
            contains_pii=contains_pii,
            contains_phi=contains_phi,
            data_classification=data_classification,
            trace_id=trace_id,
            request_id=request_id,
        )
        await self.log(event)

    async def log_agent_action(
        self,
        *,
        agent_id: str,
        action: AuditAction,
        outcome: AuditOutcome,
        org_id: str | None = None,
        tool_name: str | None = None,
        model_provider: str | None = None,
        model_name: str | None = None,
        tokens_used: int | None = None,
        cost_usd: Decimal | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log an agent/AI action for AI governance."""
        event = AuditEvent(
            actor_id=agent_id,
            actor_type=ActorType.AGENT,
            action=action,
            outcome=outcome,
            resource_type="agent_action",
            resource_id=tool_name or agent_id,
            org_id=org_id,
            trace_id=trace_id,
            request_id=request_id,
            details={
                **(details or {}),
                "tool_name": tool_name,
                "model_provider": model_provider,
                "model_name": model_name,
                "tokens_used": tokens_used,
                "cost_usd": str(cost_usd) if cost_usd else None,
            },
        )
        await self.log(event)


# Global audit logger instance
audit_logger = AuditLogger()


# Convenience functions
async def audit_log(event: AuditEvent) -> None:
    """Log an audit event using the global logger."""
    await audit_logger.log(event)


async def audit_api_call(**kwargs) -> None:
    """Log an API call using the global logger."""
    await audit_logger.log_api_call(**kwargs)


async def audit_auth_event(**kwargs) -> None:
    """Log an authentication event using the global logger."""
    await audit_logger.log_auth_event(**kwargs)


async def audit_data_access(**kwargs) -> None:
    """Log a data access event using the global logger."""
    await audit_logger.log_data_access(**kwargs)


async def audit_agent_action(**kwargs) -> None:
    """Log an agent action using the global logger."""
    await audit_logger.log_agent_action(**kwargs)

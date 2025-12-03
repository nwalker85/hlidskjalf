"""CloudEvents publisher for event-driven architecture.

Implements the CloudEvents specification (https://cloudevents.io/) for
standardized event publishing across the platform.

Events can be published to Kafka topics or external webhooks.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from cloudevents.http import CloudEvent
from cloudevents.conversion import to_json

from app.core.config import settings
from app.core.logging import get_logger
from app.core.kafka import publish

logger = get_logger(__name__)

# CloudEvents source identifier for this service
EVENT_SOURCE = f"/{settings.SERVICE_NAME}/{settings.ENVIRONMENT}"


class EventType:
    """Standard event types following naming convention.

    Format: {domain}.{entity}.{action}
    Examples:
    - platform.user.created
    - platform.org.updated
    - agent.task.completed
    """

    # User events
    USER_CREATED = "platform.user.created"
    USER_UPDATED = "platform.user.updated"
    USER_DELETED = "platform.user.deleted"

    # Organization events
    ORG_CREATED = "platform.org.created"
    ORG_UPDATED = "platform.org.updated"
    ORG_DELETED = "platform.org.deleted"

    # Authentication events
    AUTH_LOGIN = "platform.auth.login"
    AUTH_LOGOUT = "platform.auth.logout"
    AUTH_TOKEN_REFRESH = "platform.auth.token_refresh"

    # Agent events
    AGENT_TASK_STARTED = "agent.task.started"
    AGENT_TASK_COMPLETED = "agent.task.completed"
    AGENT_TASK_FAILED = "agent.task.failed"
    AGENT_TOOL_CALLED = "agent.tool.called"
    AGENT_LLM_INFERENCE = "agent.llm.inference"

    # Data events
    DATA_CREATED = "data.record.created"
    DATA_UPDATED = "data.record.updated"
    DATA_DELETED = "data.record.deleted"
    DATA_EXPORTED = "data.export.completed"

    # System events
    SYSTEM_HEALTH_CHANGED = "system.health.changed"
    SYSTEM_CONFIG_CHANGED = "system.config.changed"


class CloudEventPublisher:
    """Publisher for CloudEvents-compliant events.

    Events are published to Kafka topics based on event type.
    Each event includes standard CloudEvents attributes plus
    custom extensions for tracing and multi-tenancy.
    """

    # Map event type prefixes to Kafka topics
    TOPIC_MAPPING = {
        "platform.user": "events.platform.users",
        "platform.org": "events.platform.orgs",
        "platform.auth": "events.platform.auth",
        "agent": "events.agent",
        "data": "events.data",
        "system": "events.system",
    }

    DEFAULT_TOPIC = "events.default"

    def __init__(self):
        self._source = EVENT_SOURCE

    def _get_topic_for_event(self, event_type: str) -> str:
        """Determine the Kafka topic for an event type."""
        for prefix, topic in self.TOPIC_MAPPING.items():
            if event_type.startswith(prefix):
                return topic
        return self.DEFAULT_TOPIC

    def create_event(
        self,
        event_type: str,
        data: dict[str, Any],
        subject: str | None = None,
        *,
        org_id: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
    ) -> CloudEvent:
        """Create a CloudEvent with standard attributes.

        Args:
            event_type: The type of event (e.g., "platform.user.created")
            data: The event payload
            subject: Optional subject identifier (e.g., user ID)
            org_id: Organization ID for tenant context
            trace_id: OpenTelemetry trace ID
            request_id: Request ID for correlation
            correlation_id: ID to correlate related events

        Returns:
            CloudEvent instance ready for publishing
        """
        # CloudEvents required attributes
        attributes = {
            "specversion": "1.0",
            "type": event_type,
            "source": self._source,
            "id": str(uuid4()),
            "time": datetime.now(timezone.utc).isoformat(),
            "datacontenttype": "application/json",
        }

        # Optional subject (identifies what the event is about)
        if subject:
            attributes["subject"] = subject

        # Custom extensions for multi-tenancy and tracing
        if org_id:
            attributes["orgid"] = org_id
        if trace_id:
            attributes["traceid"] = trace_id
        if request_id:
            attributes["requestid"] = request_id
        if correlation_id:
            attributes["correlationid"] = correlation_id

        return CloudEvent(attributes, data)

    async def publish(
        self,
        event_type: str,
        data: dict[str, Any],
        subject: str | None = None,
        *,
        org_id: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
        topic: str | None = None,
    ) -> str:
        """Publish a CloudEvent to Kafka.

        Args:
            event_type: The type of event
            data: The event payload
            subject: Optional subject identifier
            org_id: Organization ID for tenant context
            trace_id: OpenTelemetry trace ID
            request_id: Request ID for correlation
            correlation_id: ID to correlate related events
            topic: Override the default topic selection

        Returns:
            The event ID
        """
        event = self.create_event(
            event_type=event_type,
            data=data,
            subject=subject,
            org_id=org_id,
            trace_id=trace_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )

        # Determine target topic
        target_topic = topic or self._get_topic_for_event(event_type)

        # Convert CloudEvent to JSON dict for Kafka
        event_dict = {
            "specversion": event["specversion"],
            "type": event["type"],
            "source": event["source"],
            "id": event["id"],
            "time": event["time"],
            "datacontenttype": event["datacontenttype"],
            "data": event.data,
        }

        # Add optional attributes
        for attr in ["subject", "orgid", "traceid", "requestid", "correlationid"]:
            if attr in event:
                event_dict[attr] = event[attr]

        try:
            await publish(
                topic=target_topic,
                value=event_dict,
                key=org_id or "system",
            )
            logger.debug(
                "CloudEvent published",
                event_id=event["id"],
                event_type=event_type,
                topic=target_topic,
                subject=subject,
            )
            return event["id"]
        except Exception as e:
            logger.error(
                "Failed to publish CloudEvent",
                event_type=event_type,
                topic=target_topic,
                error=str(e),
            )
            raise

    async def publish_user_event(
        self,
        action: str,
        user_id: str,
        user_data: dict[str, Any],
        *,
        org_id: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
    ) -> str:
        """Publish a user lifecycle event."""
        event_type = f"platform.user.{action}"
        return await self.publish(
            event_type=event_type,
            data=user_data,
            subject=user_id,
            org_id=org_id,
            trace_id=trace_id,
            request_id=request_id,
        )

    async def publish_agent_event(
        self,
        action: str,
        agent_id: str,
        data: dict[str, Any],
        *,
        org_id: str | None = None,
        trace_id: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
    ) -> str:
        """Publish an agent-related event."""
        event_type = f"agent.{action}"
        return await self.publish(
            event_type=event_type,
            data=data,
            subject=agent_id,
            org_id=org_id,
            trace_id=trace_id,
            request_id=request_id,
            correlation_id=correlation_id,
        )


# Global event publisher instance
event_publisher = CloudEventPublisher()


# Convenience functions
async def publish_event(
    event_type: str,
    data: dict[str, Any],
    subject: str | None = None,
    **kwargs: Any,
) -> str:
    """Publish a CloudEvent using the global publisher."""
    return await event_publisher.publish(
        event_type=event_type,
        data=data,
        subject=subject,
        **kwargs,
    )


async def publish_user_created(
    user_id: str, user_data: dict[str, Any], **kwargs: Any
) -> str:
    """Publish a user created event."""
    return await event_publisher.publish_user_event(
        action="created",
        user_id=user_id,
        user_data=user_data,
        **kwargs,
    )


async def publish_agent_task_completed(
    agent_id: str,
    task_data: dict[str, Any],
    **kwargs: Any,
) -> str:
    """Publish an agent task completed event."""
    return await event_publisher.publish_agent_event(
        action="task.completed",
        agent_id=agent_id,
        data=task_data,
        **kwargs,
    )

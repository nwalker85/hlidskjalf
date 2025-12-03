"""
Kafka Event Producer - Durable event emission

Uses Kafka/Redpanda for durable, replayable events.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.memory.events.schemas import RavenEvent, EventType

logger = logging.getLogger(__name__)


# Topic mapping for different event types
TOPIC_MAPPING = {
    # Huginn events go to state topic
    EventType.HUGINN_TURN: "raven.state.turns",
    EventType.HUGINN_SESSION_START: "raven.state.sessions",
    EventType.HUGINN_SESSION_END: "raven.state.sessions",
    EventType.HUGINN_INTENT: "raven.state.intents",
    
    # Frigg events go to context topic
    EventType.FRIGG_PERSONA_UPDATED: "raven.context.personas",
    EventType.FRIGG_PERSONA_CREATED: "raven.context.personas",
    EventType.FRIGG_RISK_FLAG: "raven.context.risks",
    
    # Muninn events go to memory topic
    EventType.MUNINN_MEMORY_CREATED: "raven.memory.episodes",
    EventType.MUNINN_MEMORY_RECALLED: "raven.memory.recalls",
    EventType.MUNINN_EPISODE_START: "raven.memory.episodes",
    EventType.MUNINN_EPISODE_END: "raven.memory.episodes",
    
    # Hel events go to governance topic
    EventType.HEL_MEMORY_REINFORCED: "raven.governance.reinforcements",
    EventType.HEL_MEMORY_DECAYED: "raven.governance.decay",
    EventType.HEL_MEMORY_PROMOTED: "raven.governance.promotions",
    EventType.HEL_MEMORY_FORGOTTEN: "raven.governance.pruned",
    EventType.HEL_DECAY_CYCLE: "raven.governance.cycles",
    
    # Mímir events go to domain topic
    EventType.MIMIR_DOSSIER_LOADED: "raven.domain.dossiers",
    EventType.MIMIR_DOSSIER_CHANGED: "raven.domain.changes",
    EventType.MIMIR_TRIPLET_EXECUTED: "raven.domain.executions",
}


class KafkaEventProducer:
    """
    Kafka/Redpanda producer for durable events.
    
    Used for:
    - Audit trail (compliance)
    - Event replay for debugging
    - Cross-service coordination
    - Memory candidate submission
    """
    
    def __init__(
        self,
        bootstrap_servers: str = "redpanda:9092",  # Docker service name
        client_id: str = "raven-producer",
    ):
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        
        self._producer = None
        self._connected = False
    
    async def connect(self) -> bool:
        """Connect to Kafka"""
        try:
            from aiokafka import AIOKafkaProducer
            
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                value_serializer=lambda v: json.dumps(v).encode(),
            )
            await self._producer.start()
            
            self._connected = True
            logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
            return True
            
        except ImportError:
            logger.warning("aiokafka not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            return False
    
    async def publish(self, event: RavenEvent) -> bool:
        """
        Publish an event to Kafka.
        
        Topic is determined by event type.
        Key is session_id for partitioning.
        """
        if not self._producer:
            logger.warning("Kafka not connected")
            return False
        
        topic = TOPIC_MAPPING.get(event.event_type, "raven.events.default")
        key = event.session_id.encode() if event.session_id else None
        
        try:
            await self._producer.send_and_wait(
                topic,
                event.model_dump(),
                key=key,
            )
            logger.debug(f"Published to Kafka topic {topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to Kafka: {e}")
            return False
    
    async def publish_to_topic(
        self,
        topic: str,
        data: dict[str, Any],
        key: str | None = None,
    ) -> bool:
        """Publish raw data to a specific topic"""
        if not self._producer:
            return False
        
        try:
            await self._producer.send_and_wait(
                topic,
                data,
                key=key.encode() if key else None,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to publish to topic {topic}: {e}")
            return False
    
    async def close(self) -> None:
        """Close Kafka connection"""
        if self._producer:
            await self._producer.stop()
            self._producer = None
            self._connected = False
            logger.info("Kafka connection closed")
    
    @property
    def is_connected(self) -> bool:
        return self._connected


class DualEventProducer:
    """
    Combined producer for both NATS and Kafka.
    
    Publishes to NATS for hot-path and Kafka for durability.
    """
    
    def __init__(
        self,
        nats_url: str = "nats://nats:4222",  # Docker service name
        kafka_bootstrap: str = "redpanda:9092",  # Docker service name
    ):
        from src.memory.events.nats_producer import NATSEventProducer
        
        self.nats = NATSEventProducer(nats_url)
        self.kafka = KafkaEventProducer(kafka_bootstrap)
    
    async def connect(self) -> bool:
        """Connect to both NATS and Kafka"""
        nats_ok = await self.nats.connect()
        kafka_ok = await self.kafka.connect()
        return nats_ok or kafka_ok  # At least one should work
    
    async def publish(self, event: RavenEvent) -> bool:
        """Publish to both NATS and Kafka"""
        nats_ok = await self.nats.publish(event)
        kafka_ok = await self.kafka.publish(event)
        return nats_ok or kafka_ok
    
    async def close(self) -> None:
        """Close both connections"""
        await self.nats.close()
        await self.kafka.close()


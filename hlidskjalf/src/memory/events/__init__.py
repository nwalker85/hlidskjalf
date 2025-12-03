"""
Event Fabric - The Wind that carries signals

Dual-stream event system:
- NATS JetStream: Hot-path, millisecond latency
- Kafka/Redpanda: Durable, replayable, auditable
"""

from src.memory.events.nats_producer import NATSEventProducer
from src.memory.events.kafka_producer import KafkaEventProducer
from src.memory.events.schemas import (
    RavenEvent,
    HuginnTurnEvent,
    FriggPersonaEvent,
    MuninnMemoryEvent,
    HelDecayEvent,
    MimirDomainEvent,
)

__all__ = [
    "NATSEventProducer",
    "KafkaEventProducer",
    "RavenEvent",
    "HuginnTurnEvent",
    "FriggPersonaEvent",
    "MuninnMemoryEvent",
    "HelDecayEvent",
    "MimirDomainEvent",
]


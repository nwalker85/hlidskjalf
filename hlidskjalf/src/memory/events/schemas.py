"""
Event Schemas - Pydantic models for all Raven events
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Event types in the Raven system"""
    # Huginn events
    HUGINN_TURN = "huginn.turn"
    HUGINN_SESSION_START = "huginn.session.start"
    HUGINN_SESSION_END = "huginn.session.end"
    HUGINN_INTENT = "huginn.intent"
    
    # Frigg events
    FRIGG_PERSONA_UPDATED = "frigg.persona.updated"
    FRIGG_PERSONA_CREATED = "frigg.persona.created"
    FRIGG_RISK_FLAG = "frigg.risk.flag"
    
    # Muninn events
    MUNINN_MEMORY_CREATED = "muninn.memory.created"
    MUNINN_MEMORY_RECALLED = "muninn.memory.recalled"
    MUNINN_EPISODE_START = "muninn.episode.start"
    MUNINN_EPISODE_END = "muninn.episode.end"
    
    # Hel events
    HEL_MEMORY_REINFORCED = "hel.memory.reinforced"
    HEL_MEMORY_DECAYED = "hel.memory.decayed"
    HEL_MEMORY_PROMOTED = "hel.memory.promoted"
    HEL_MEMORY_FORGOTTEN = "hel.memory.forgotten"
    HEL_DECAY_CYCLE = "hel.decay.cycle"
    
    # Mímir events
    MIMIR_DOSSIER_LOADED = "mimir.dossier.loaded"
    MIMIR_DOSSIER_CHANGED = "mimir.dossier.changed"
    MIMIR_TRIPLET_EXECUTED = "mimir.triplet.executed"


class RavenEvent(BaseModel):
    """Base event model for all Raven events"""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Correlation
    session_id: str | None = None
    user_id: str | None = None
    trace_id: str | None = None
    
    # Payload
    payload: dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    source: str = "raven"
    version: str = "1.0"


class HuginnTurnEvent(RavenEvent):
    """Turn-level event from Huginn"""
    event_type: EventType = EventType.HUGINN_TURN
    
    # Turn data
    utterance: str = ""
    intent: str | None = None
    slots: dict[str, Any] = Field(default_factory=dict)
    workflow_step: str | None = None


class FriggPersonaEvent(RavenEvent):
    """Persona update event from Frigg"""
    event_type: EventType = EventType.FRIGG_PERSONA_UPDATED
    
    # Persona data
    tags: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    risk_flags: dict[str, bool] = Field(default_factory=dict)
    memory_refs: list[str] = Field(default_factory=list)


class MuninnMemoryEvent(RavenEvent):
    """Memory event from Muninn"""
    event_type: EventType = EventType.MUNINN_MEMORY_CREATED
    
    # Memory data
    memory_id: str = ""
    memory_type: str = "episodic"
    domain: str = "general"
    content_preview: str = ""
    weight: float = 0.5


class HelDecayEvent(RavenEvent):
    """Decay/governance event from Hel"""
    event_type: EventType = EventType.HEL_DECAY_CYCLE
    
    # Decay stats
    memories_processed: int = 0
    memories_decayed: int = 0
    memories_promoted: int = 0
    memories_pruned: int = 0


class MimirDomainEvent(RavenEvent):
    """Domain intelligence event from Mímir"""
    event_type: EventType = EventType.MIMIR_DOSSIER_LOADED
    
    # Dossier data
    dossier_id: str = ""
    dossier_name: str = ""
    entity_count: int = 0
    role_count: int = 0
    triplet_count: int = 0


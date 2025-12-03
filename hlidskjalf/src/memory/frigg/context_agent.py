"""
Frigg Context Agent - The Queen Who Knows All Fates

Builds and maintains PersonaSnapshots for user sessions.
Integrates state from Huginn, memory from Muninn, and knowledge from Mímir.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from src.memory.frigg.persona_snapshot import (
    PersonaSnapshot,
    PersonaBuilder,
    EpisodeRef,
)
from src.memory.frigg.context_cache import FriggContextCache

logger = logging.getLogger(__name__)


class StateEvent(BaseModel):
    """Event from Huginn with state updates"""
    session_id: str
    user_id: str
    intent: str | None = None
    slots: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class FriggContextAgent:
    """
    Frigg knows all fates but speaks them not - until asked.
    
    Responsibilities:
    - Build PersonaSnapshots from state events
    - Enrich with user preferences from PostgresStore
    - Retrieve relevant episodes from Muninn
    - Fetch applicable triplets from Mímir
    - Cache snapshots for zero-latency access
    - Emit persona.updated events to Kafka
    """
    
    def __init__(
        self,
        store=None,  # PostgresStore for user profiles
        muninn=None,  # MuninnStore for memory
        mimir=None,   # MimirTripletEngine for domain knowledge
        kafka_bootstrap: str | None = None,
    ):
        self.store = store
        self.muninn = muninn
        self.mimir = mimir
        self.kafka_bootstrap = kafka_bootstrap
        
        # Local cache for zero-latency reads
        self.context_cache = FriggContextCache()
        
        # Kafka producer (lazy init)
        self._kafka_producer = None
    
    async def _get_kafka(self):
        """Lazy Kafka producer"""
        if self._kafka_producer is None and self.kafka_bootstrap:
            try:
                from aiokafka import AIOKafkaProducer
                self._kafka_producer = AIOKafkaProducer(
                    bootstrap_servers=self.kafka_bootstrap
                )
                await self._kafka_producer.start()
            except ImportError:
                logger.warning("aiokafka not installed, Kafka events disabled")
        return self._kafka_producer
    
    async def on_state_event(self, event: StateEvent) -> PersonaSnapshot:
        """
        Build/update persona from state changes.
        
        Called when Huginn emits state updates.
        """
        session_id = event.session_id
        user_id = event.user_id
        
        # Start building persona
        builder = PersonaBuilder(session_id, user_id)
        
        # 1. Get user preferences from store
        preferences = await self._get_preferences(user_id)
        for key, value in preferences.items():
            builder.with_preference(key, value)
        
        # 2. Get user profile and tags
        profile = await self._get_user_profile(user_id)
        for tag in profile.get("tags", []):
            builder.with_tags(tag)
        
        # 3. Apply risk assessment
        risk_flags = await self._assess_risks(event, profile)
        for flag, value in risk_flags.items():
            builder.with_risk_flag(flag, value)
        
        # 4. Get recent episodes from Muninn
        episodes = await self._get_recent_episodes(user_id)
        for ep in episodes:
            builder.with_episode(ep)
        
        # 5. Get relevant memories
        memory_refs = await self._get_relevant_memories(event)
        for ref in memory_refs:
            builder.with_memory_ref(ref)
        
        # 6. Determine current role
        role = self._determine_role(event, profile)
        if role:
            builder.with_role(role)
        
        # 7. Get applicable triplets from Mímir
        if self.mimir and role:
            context = {
                "session": {"intent": event.intent, "slots": event.slots},
                "user": profile,
            }
            triplets = self.mimir.consult(role, context)
            for t in triplets:
                builder.with_triplets(t.triplet_id if hasattr(t, 'triplet_id') else str(t))
        
        # Build the snapshot
        snapshot = builder.build()
        
        # Cache it
        self.context_cache.set(session_id, snapshot)
        
        # Emit to Kafka
        await self._emit_persona_updated(snapshot)
        
        logger.debug(f"Frigg built persona for session {session_id}")
        return snapshot
    
    async def _get_preferences(self, user_id: str) -> dict[str, Any]:
        """Get user preferences from store"""
        if not self.store:
            return {}
        
        try:
            result = await self.store.aget(("users", user_id), "preferences")
            return result.value if result else {}
        except Exception as e:
            logger.error(f"Failed to get preferences: {e}")
            return {}
    
    async def _get_user_profile(self, user_id: str) -> dict[str, Any]:
        """Get full user profile from store"""
        if not self.store:
            return {}
        
        try:
            result = await self.store.aget(("users", user_id), "profile")
            return result.value if result else {}
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return {}
    
    async def _assess_risks(
        self, 
        event: StateEvent, 
        profile: dict[str, Any]
    ) -> dict[str, bool]:
        """Assess risk flags based on event and profile"""
        risks = {}
        
        # Check profile for existing flags
        if profile.get("is_vulnerable"):
            risks["vulnerability"] = True
        
        if profile.get("fraud_history"):
            risks["fraud_risk"] = True
        
        # Intent-based risk assessment
        if event.intent in ["dispute", "complaint", "cancel"]:
            risks["escalation_risk"] = True
        
        return risks
    
    async def _get_recent_episodes(self, user_id: str, limit: int = 5) -> list[EpisodeRef]:
        """Get recent interaction episodes from Muninn"""
        if not self.muninn:
            return []
        
        try:
            episodes = await self.muninn.get_user_episodes(user_id, limit=limit)
            return [
                EpisodeRef(
                    episode_id=ep.id,
                    timestamp=ep.timestamp,
                    topic=ep.topic,
                    summary=ep.summary,
                    relevance_score=1.0,
                )
                for ep in episodes
            ]
        except Exception as e:
            logger.error(f"Failed to get episodes: {e}")
            return []
    
    async def _get_relevant_memories(self, event: StateEvent) -> list[str]:
        """Get relevant memory references based on current context"""
        if not self.muninn:
            return []
        
        try:
            # Search memories by intent/context
            query = event.intent or ""
            memories = await self.muninn.recall(query, k=5)
            return [m.id for m in memories]
        except Exception as e:
            logger.error(f"Failed to get relevant memories: {e}")
            return []
    
    def _determine_role(self, event: StateEvent, profile: dict[str, Any]) -> str | None:
        """Determine current user role"""
        # Check profile for explicit role
        if "role" in profile:
            return profile["role"]
        
        # Default role based on channel or context
        channel = profile.get("channel", "default")
        return f"user_{channel}"
    
    async def _emit_persona_updated(self, snapshot: PersonaSnapshot) -> None:
        """Emit persona.updated event to Kafka"""
        try:
            producer = await self._get_kafka()
            if producer:
                await producer.send_and_wait(
                    "frigg.persona.updated",
                    snapshot.model_dump_json().encode()
                )
        except Exception as e:
            logger.error(f"Failed to emit persona event: {e}")
    
    def divine(self, session_id: str) -> PersonaSnapshot | None:
        """
        What does Frigg know of this user's fate?
        
        Zero-latency local cache lookup.
        This is the hot-path read.
        """
        return self.context_cache.get(session_id)
    
    async def divine_with_fallback(self, session_id: str, user_id: str) -> PersonaSnapshot:
        """
        Divine with store fallback if not in cache.
        
        Use for cold starts. Not recommended for hot path.
        """
        # Try local cache first
        snapshot = self.divine(session_id)
        if snapshot:
            return snapshot
        
        # Build fresh persona
        event = StateEvent(session_id=session_id, user_id=user_id)
        return await self.on_state_event(event)
    
    async def update_tags(self, session_id: str, *tags: str) -> PersonaSnapshot | None:
        """Add tags to a persona"""
        snapshot = self.divine(session_id)
        if not snapshot:
            return None
        
        for tag in tags:
            if tag not in snapshot.tags:
                snapshot.tags.append(tag)
        
        snapshot.last_updated = datetime.now(timezone.utc)
        self.context_cache.set(session_id, snapshot)
        await self._emit_persona_updated(snapshot)
        
        return snapshot
    
    async def set_risk_flag(
        self, 
        session_id: str, 
        flag: str, 
        value: bool = True
    ) -> PersonaSnapshot | None:
        """Set a risk flag on persona"""
        snapshot = self.divine(session_id)
        if not snapshot:
            return None
        
        snapshot.risk_flags[flag] = value
        snapshot.last_updated = datetime.now(timezone.utc)
        self.context_cache.set(session_id, snapshot)
        await self._emit_persona_updated(snapshot)
        
        return snapshot
    
    async def clear_session(self, session_id: str) -> None:
        """Clear persona for session"""
        self.context_cache.delete(session_id)
    
    async def close(self) -> None:
        """Clean up resources"""
        await self.context_cache.stop()
        if self._kafka_producer:
            await self._kafka_producer.stop()


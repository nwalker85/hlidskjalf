"""
Episodic Memory - Raw experiences and interactions

Stores personal interactions, transcripts, and user-specific experiences.
Candidates for promotion to semantic memory via Hel.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.memory.muninn.store import MuninnStore, MemoryFragment, MemoryType

logger = logging.getLogger(__name__)


class Episode(BaseModel):
    """A single interaction episode"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Context
    session_id: str
    user_id: str
    
    # Content
    topic: str
    summary: str
    transcript: list[dict[str, str]] = Field(default_factory=list)
    # [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    
    # Outcome
    outcome: str | None = None  # "resolved", "escalated", "abandoned"
    satisfaction: float | None = None  # 0.0 - 1.0
    
    # Metadata
    intent: str | None = None
    entities: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    
    # Timestamps
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    
    def duration_seconds(self) -> float | None:
        """Get episode duration in seconds"""
        if not self.ended_at:
            return None
        return (self.ended_at - self.started_at).total_seconds()
    
    def to_fragment(self) -> MemoryFragment:
        """Convert to a MemoryFragment for storage"""
        return MemoryFragment(
            id=self.id,
            type=MemoryType.EPISODIC,
            content=self.summary,
            domain=self.topic,
            topic=self.topic,
            summary=self.summary,
            user_id=self.user_id,
            session_id=self.session_id,
            features={
                "intent": self.intent,
                "outcome": self.outcome,
                "satisfaction": self.satisfaction,
                "duration": self.duration_seconds(),
                "entities": self.entities,
                "tags": self.tags,
            },
            created_at=self.started_at,
        )


class EpisodicMemory:
    """
    Manages episodic memory - raw experiences.
    
    Features:
    - Record interaction episodes
    - Track conversation transcripts
    - Extract episode summaries
    - Identify patterns for promotion
    """
    
    def __init__(self, store: MuninnStore):
        self.store = store
        self._active_episodes: dict[str, Episode] = {}
    
    async def start_episode(
        self,
        session_id: str,
        user_id: str,
        topic: str = "general",
        intent: str | None = None,
    ) -> Episode:
        """Start a new interaction episode"""
        episode = Episode(
            session_id=session_id,
            user_id=user_id,
            topic=topic,
            summary="",
            intent=intent,
        )
        self._active_episodes[session_id] = episode
        logger.debug(f"Started episode {episode.id} for session {session_id}")
        return episode
    
    def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Add a turn to the active episode"""
        episode = self._active_episodes.get(session_id)
        if episode:
            episode.transcript.append({"role": role, "content": content})
    
    def add_entity(
        self,
        session_id: str,
        entity_type: str,
        entity_value: Any,
    ) -> None:
        """Add an extracted entity to the episode"""
        episode = self._active_episodes.get(session_id)
        if episode:
            episode.entities[entity_type] = entity_value
    
    def add_tag(self, session_id: str, tag: str) -> None:
        """Add a tag to the episode"""
        episode = self._active_episodes.get(session_id)
        if episode and tag not in episode.tags:
            episode.tags.append(tag)
    
    async def end_episode(
        self,
        session_id: str,
        outcome: str | None = None,
        satisfaction: float | None = None,
    ) -> Episode | None:
        """End an episode and persist to Muninn"""
        episode = self._active_episodes.pop(session_id, None)
        if not episode:
            return None
        
        episode.ended_at = datetime.now(timezone.utc)
        episode.outcome = outcome
        episode.satisfaction = satisfaction
        
        # Generate summary from transcript
        episode.summary = self._generate_summary(episode)
        
        # Store as memory fragment
        fragment = episode.to_fragment()
        await self.store.remember(fragment)
        
        # Emit to Kafka for analysis
        await self._emit_episode_event(episode)
        
        logger.debug(f"Ended episode {episode.id}")
        return episode
    
    def _generate_summary(self, episode: Episode) -> str:
        """Generate a summary from transcript"""
        if not episode.transcript:
            return f"Interaction about {episode.topic}"
        
        # Simple summary: first user message + outcome
        first_user = next(
            (t["content"] for t in episode.transcript if t["role"] == "user"),
            ""
        )
        
        summary_parts = [f"User: {first_user[:100]}"]
        if episode.outcome:
            summary_parts.append(f"Outcome: {episode.outcome}")
        if episode.intent:
            summary_parts.append(f"Intent: {episode.intent}")
        
        return " | ".join(summary_parts)
    
    async def _emit_episode_event(self, episode: Episode) -> None:
        """Emit episode to Kafka for pattern analysis"""
        # This would emit to muninn.episodes topic
        # for Hel to analyze and potentially promote
        pass
    
    def get_active_episode(self, session_id: str) -> Episode | None:
        """Get the active episode for a session"""
        return self._active_episodes.get(session_id)
    
    async def get_user_history(
        self,
        user_id: str,
        topic: str | None = None,
        limit: int = 10,
    ) -> list[Episode]:
        """Get episode history for a user"""
        fragments = await self.store.get_user_episodes(user_id, limit)
        
        episodes = []
        for f in fragments:
            if topic and f.topic != topic:
                continue
            
            episodes.append(Episode(
                id=f.id,
                session_id=f.session_id or "",
                user_id=f.user_id or "",
                topic=f.topic or "general",
                summary=f.summary or f.content,
                intent=f.features.get("intent"),
                outcome=f.features.get("outcome"),
                satisfaction=f.features.get("satisfaction"),
                entities=f.features.get("entities", {}),
                tags=f.features.get("tags", []),
                started_at=f.created_at,
            ))
        
        return episodes
    
    async def find_similar_episodes(
        self,
        query: str,
        user_id: str | None = None,
        k: int = 5,
    ) -> list[MemoryFragment]:
        """Find episodes similar to a query"""
        return await self.store.recall(
            query=query,
            k=k,
            memory_type=MemoryType.EPISODIC,
        )


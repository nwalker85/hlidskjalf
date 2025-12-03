"""
Persona Snapshot - Frigg's knowledge of who the user is

A compact, actionable snapshot of user context that includes:
- User identity and preferences
- Recent interaction history
- Risk flags and compliance constraints
- Applicable domain actions (from Mímir)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class EpisodeRef(BaseModel):
    """Reference to a past episode/interaction"""
    episode_id: str
    timestamp: datetime
    topic: str
    summary: str | None = None
    relevance_score: float = 0.0


class PersonaSnapshot(BaseModel):
    """
    Frigg's knowledge of who the user is.
    
    This is the compact, actionable context delivered to agents
    for personalization without hot-path database lookups.
    """
    
    # Identity
    session_id: str
    user_id: str
    
    # Classification tags
    tags: list[str] = Field(default_factory=list)
    # Examples: ["repeat_caller", "billing_sensitive", "vip", "new_user"]
    
    # Recent interaction history
    recent_episodes: list[EpisodeRef] = Field(default_factory=list)
    
    # User preferences
    preferences: dict[str, Any] = Field(default_factory=dict)
    # Examples: {"language": "en-US", "tone": "formal", "channel": "voice"}
    
    # Risk and compliance flags
    risk_flags: dict[str, bool] = Field(default_factory=dict)
    # Examples: {"vulnerability": True, "fraud_risk": False}
    
    # Regulatory constraints
    regulatory_constraints: list[str] = Field(default_factory=list)
    # Examples: ["GDPR", "PCI-DSS", "HIPAA"]
    
    # References to relevant long-term memories
    memory_refs: list[str] = Field(default_factory=list)
    # Examples: ["mem_ep_001", "mem_sem_020"]
    
    # Current role (for Mímir triplet lookup)
    current_role: str | None = None
    
    # Valid actions from Mímir (AgenticTriplet IDs)
    applicable_triplets: list[str] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def has_tag(self, tag: str) -> bool:
        """Check if user has a specific tag"""
        return tag in self.tags
    
    def has_risk(self, risk: str) -> bool:
        """Check if user has a specific risk flag"""
        return self.risk_flags.get(risk, False)
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference with default"""
        return self.preferences.get(key, default)
    
    def is_constrained_by(self, regulation: str) -> bool:
        """Check if user is under a specific regulation"""
        return regulation in self.regulatory_constraints
    
    def to_context_dict(self) -> dict[str, Any]:
        """Convert to a dictionary suitable for LLM context"""
        return {
            "user_id": self.user_id,
            "tags": self.tags,
            "preferences": self.preferences,
            "risk_flags": {k: v for k, v in self.risk_flags.items() if v},
            "constraints": self.regulatory_constraints,
            "recent_topics": [ep.topic for ep in self.recent_episodes[:5]],
            "available_actions": self.applicable_triplets,
        }


class PersonaBuilder:
    """Builder pattern for constructing PersonaSnapshots"""
    
    def __init__(self, session_id: str, user_id: str):
        self._snapshot = PersonaSnapshot(session_id=session_id, user_id=user_id)
    
    def with_tags(self, *tags: str) -> PersonaBuilder:
        self._snapshot.tags.extend(tags)
        return self
    
    def with_preference(self, key: str, value: Any) -> PersonaBuilder:
        self._snapshot.preferences[key] = value
        return self
    
    def with_risk_flag(self, flag: str, value: bool = True) -> PersonaBuilder:
        self._snapshot.risk_flags[flag] = value
        return self
    
    def with_constraint(self, constraint: str) -> PersonaBuilder:
        if constraint not in self._snapshot.regulatory_constraints:
            self._snapshot.regulatory_constraints.append(constraint)
        return self
    
    def with_episode(self, episode: EpisodeRef) -> PersonaBuilder:
        self._snapshot.recent_episodes.append(episode)
        return self
    
    def with_memory_ref(self, ref: str) -> PersonaBuilder:
        self._snapshot.memory_refs.append(ref)
        return self
    
    def with_role(self, role: str) -> PersonaBuilder:
        self._snapshot.current_role = role
        return self
    
    def with_triplets(self, *triplet_ids: str) -> PersonaBuilder:
        self._snapshot.applicable_triplets.extend(triplet_ids)
        return self
    
    def build(self) -> PersonaSnapshot:
        self._snapshot.last_updated = datetime.now(timezone.utc)
        return self._snapshot


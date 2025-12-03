"""
Semantic Memory - Learned patterns and stable knowledge

Stores:
- Patterns extracted from episodes
- Stable correlations
- Action-outcome mappings
- Domain-specific knowledge

Derived from episodic memory through consolidation (Hel promotion).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.memory.muninn.store import MuninnStore, MemoryFragment, MemoryType

logger = logging.getLogger(__name__)


class Pattern(BaseModel):
    """A learned pattern or correlation"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Pattern definition
    pattern_type: str  # "action_outcome", "user_behavior", "domain_rule", "workflow"
    description: str
    
    # Confidence and evidence
    confidence: float = 0.5  # 0.0 - 1.0
    evidence_count: int = 0
    source_episodes: list[str] = Field(default_factory=list)
    
    # Domain and scope
    domain: str = "general"
    scope: str = "global"  # "global", "user", "session"
    
    # Pattern data
    conditions: dict[str, Any] = Field(default_factory=dict)
    outcomes: dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    tags: list[str] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_validated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_fragment(self) -> MemoryFragment:
        """Convert to a MemoryFragment for storage"""
        return MemoryFragment(
            id=self.id,
            type=MemoryType.SEMANTIC,
            content=self.description,
            domain=self.domain,
            topic=self.pattern_type,
            summary=f"{self.pattern_type}: {self.description[:100]}",
            weight=self.confidence,
            references=self.evidence_count,
            source_keys=self.source_episodes,
            features={
                "pattern_type": self.pattern_type,
                "conditions": self.conditions,
                "outcomes": self.outcomes,
                "scope": self.scope,
                "tags": self.tags,
            },
            created_at=self.created_at,
            last_used=self.last_validated,
        )


class SemanticMemory:
    """
    Manages semantic memory - learned patterns.
    
    Features:
    - Store and retrieve patterns
    - Match patterns to contexts
    - Track pattern confidence
    - Support pattern evolution
    """
    
    def __init__(self, store: MuninnStore):
        self.store = store
    
    async def add_pattern(self, pattern: Pattern) -> str:
        """Add a new pattern to semantic memory"""
        fragment = pattern.to_fragment()
        await self.store.remember(fragment)
        logger.debug(f"Added pattern {pattern.id}: {pattern.pattern_type}")
        return pattern.id
    
    async def get_pattern(self, pattern_id: str) -> Pattern | None:
        """Get a specific pattern by ID"""
        fragment = await self.store.get(pattern_id)
        if not fragment or fragment.type != MemoryType.SEMANTIC:
            return None
        return self._fragment_to_pattern(fragment)
    
    def _fragment_to_pattern(self, fragment: MemoryFragment) -> Pattern:
        """Convert a MemoryFragment to a Pattern"""
        return Pattern(
            id=fragment.id,
            pattern_type=fragment.features.get("pattern_type", "unknown"),
            description=fragment.content,
            confidence=fragment.weight,
            evidence_count=fragment.references,
            source_episodes=fragment.source_keys,
            domain=fragment.domain,
            scope=fragment.features.get("scope", "global"),
            conditions=fragment.features.get("conditions", {}),
            outcomes=fragment.features.get("outcomes", {}),
            tags=fragment.features.get("tags", []),
            created_at=fragment.created_at,
            last_validated=fragment.last_used,
        )
    
    async def find_patterns(
        self,
        query: str,
        pattern_type: str | None = None,
        domain: str | None = None,
        min_confidence: float = 0.3,
        k: int = 5,
    ) -> list[Pattern]:
        """Find patterns matching a query"""
        fragments = await self.store.recall(
            query=query,
            k=k,
            memory_type=MemoryType.SEMANTIC,
            domain=domain,
            min_weight=min_confidence,
        )
        
        patterns = [self._fragment_to_pattern(f) for f in fragments]
        
        # Filter by pattern type if specified
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        
        return patterns
    
    async def match_context(
        self,
        context: dict[str, Any],
        domain: str | None = None,
    ) -> list[Pattern]:
        """Find patterns that match a given context"""
        # Convert context to query string
        query_parts = []
        for key, value in context.items():
            if isinstance(value, str):
                query_parts.append(value)
            elif isinstance(value, list):
                query_parts.extend(str(v) for v in value)
        
        query = " ".join(query_parts)
        return await self.find_patterns(query, domain=domain)
    
    async def validate_pattern(
        self,
        pattern_id: str,
        success: bool,
    ) -> Pattern | None:
        """Update pattern confidence based on validation"""
        pattern = await self.get_pattern(pattern_id)
        if not pattern:
            return None
        
        # Update confidence based on validation
        if success:
            # Increase confidence
            pattern.confidence = min(1.0, pattern.confidence + 0.05)
        else:
            # Decrease confidence
            pattern.confidence = max(0.0, pattern.confidence - 0.1)
        
        pattern.evidence_count += 1
        pattern.last_validated = datetime.now(timezone.utc)
        
        # Update in store
        fragment = pattern.to_fragment()
        await self.store.remember(fragment)
        
        return pattern
    
    async def promote_from_episodes(
        self,
        episode_ids: list[str],
        pattern_type: str,
        description: str,
        conditions: dict[str, Any],
        outcomes: dict[str, Any],
        domain: str = "general",
    ) -> Pattern:
        """
        Create a new pattern from multiple episodes.
        
        This is called by Hel during promotion.
        """
        pattern = Pattern(
            pattern_type=pattern_type,
            description=description,
            confidence=0.6,  # Initial confidence
            evidence_count=len(episode_ids),
            source_episodes=episode_ids,
            domain=domain,
            conditions=conditions,
            outcomes=outcomes,
        )
        
        await self.add_pattern(pattern)
        logger.info(f"Promoted pattern {pattern.id} from {len(episode_ids)} episodes")
        
        return pattern
    
    async def get_domain_patterns(
        self,
        domain: str,
        min_confidence: float = 0.5,
    ) -> list[Pattern]:
        """Get all patterns for a domain"""
        fragments = await self.store.recall(
            query=domain,
            k=100,
            memory_type=MemoryType.SEMANTIC,
            domain=domain,
            min_weight=min_confidence,
        )
        return [self._fragment_to_pattern(f) for f in fragments]


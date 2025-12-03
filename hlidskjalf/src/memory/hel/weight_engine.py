"""
Hel Weight Engine - Memory reinforcement and decay

Implements the cognitive model for memory importance:
- Reinforcement when memories are referenced/useful
- Exponential decay over time
- Promotion criteria from episodic to semantic
- Pruning criteria for forgotten memories
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from src.memory.muninn.store import MemoryFragment, MemoryType

logger = logging.getLogger(__name__)


class HelWeightEngine:
    """
    Hel governs what memories live and what fades.
    
    Weighting model:
    - weight ∈ [0.0, 1.0]
    - Reinforcement: weight += α * importance
    - Decay: weight *= e^(-λ * time)
    
    Default parameters calibrated for:
    - α = 0.1 (reinforcement rate)
    - λ = 0.001 (slow decay, ~30% after 24h without use)
    """
    
    def __init__(
        self,
        alpha: float = 0.1,   # Reinforcement rate
        lambda_: float = 0.001,  # Decay rate (per hour)
        promotion_threshold: float = 0.8,
        promotion_min_references: int = 3,
        prune_threshold: float = 0.1,
        prune_min_age_hours: float = 24.0,
    ):
        self.alpha = alpha
        self.lambda_ = lambda_
        self.promotion_threshold = promotion_threshold
        self.promotion_min_references = promotion_min_references
        self.prune_threshold = prune_threshold
        self.prune_min_age_hours = prune_min_age_hours
    
    def reinforce(
        self,
        memory: MemoryFragment,
        importance: float = 1.0,
        reason: str | None = None,
    ) -> float:
        """
        Strengthen a memory that proved useful.
        
        Called when:
        - Memory is referenced during a session
        - Memory helps produce a successful response
        - Cross-domain correlation detected
        
        Returns the new weight.
        """
        old_weight = memory.weight
        
        # Apply reinforcement
        delta = self.alpha * importance
        memory.weight = min(1.0, memory.weight + delta)
        
        # Update reference count and timestamp
        memory.references += 1
        memory.last_used = datetime.now(timezone.utc)
        
        logger.debug(
            f"Hel reinforced memory {memory.id}: "
            f"{old_weight:.3f} -> {memory.weight:.3f} "
            f"(reason: {reason or 'reference'})"
        )
        
        return memory.weight
    
    def decay(self, memory: MemoryFragment) -> float:
        """
        Apply time-based decay to a memory.
        
        Decay follows: weight *= e^(-λ * hours_since_use)
        
        Returns the new weight.
        """
        hours_since_use = memory.age_hours()
        
        if hours_since_use <= 0:
            return memory.weight
        
        old_weight = memory.weight
        decay_factor = math.exp(-self.lambda_ * hours_since_use)
        memory.weight = memory.weight * decay_factor
        
        if old_weight - memory.weight > 0.01:
            logger.debug(
                f"Hel decayed memory {memory.id}: "
                f"{old_weight:.3f} -> {memory.weight:.3f} "
                f"(hours: {hours_since_use:.1f})"
            )
        
        return memory.weight
    
    def should_promote(self, memory: MemoryFragment) -> bool:
        """
        Check if an episodic memory should ascend to semantic.
        
        Criteria:
        - Must be episodic type
        - Weight above promotion threshold
        - Minimum number of references
        """
        if memory.type != MemoryType.EPISODIC:
            return False
        
        if memory.weight < self.promotion_threshold:
            return False
        
        if memory.references < self.promotion_min_references:
            return False
        
        return True
    
    def should_prune(self, memory: MemoryFragment) -> bool:
        """
        Check if a memory should pass into oblivion.
        
        Criteria:
        - Weight below prune threshold
        - Old enough (minimum age)
        """
        if memory.weight >= self.prune_threshold:
            return False
        
        if memory.age_hours() < self.prune_min_age_hours:
            return False
        
        return True
    
    def calculate_importance(
        self,
        memory: MemoryFragment,
        context: dict[str, Any],
    ) -> float:
        """
        Calculate importance factor for reinforcement.
        
        Considers:
        - Domain match (higher if same domain as context)
        - Recency of creation
        - User specificity
        - Semantic relevance (if similarity score provided)
        """
        importance = 1.0
        
        # Domain match bonus
        if context.get("domain") == memory.domain:
            importance *= 1.5
        
        # User-specific memories are more important for that user
        if memory.user_id and context.get("user_id") == memory.user_id:
            importance *= 1.3
        
        # Recent memories get slight boost
        age_hours = memory.age_hours()
        if age_hours < 1:
            importance *= 1.2
        elif age_hours < 24:
            importance *= 1.1
        
        # Similarity score if provided
        similarity = context.get("similarity_score", 0.0)
        if similarity > 0:
            importance *= (1.0 + similarity * 0.5)
        
        return min(2.0, importance)  # Cap at 2x
    
    def bulk_decay(
        self,
        memories: list[MemoryFragment],
    ) -> tuple[list[MemoryFragment], list[MemoryFragment]]:
        """
        Apply decay to multiple memories and identify prune candidates.
        
        Returns (decayed_memories, prune_candidates).
        """
        decayed = []
        prune_candidates = []
        
        for memory in memories:
            self.decay(memory)
            decayed.append(memory)
            
            if self.should_prune(memory):
                prune_candidates.append(memory)
        
        return decayed, prune_candidates
    
    def get_promotion_candidates(
        self,
        memories: list[MemoryFragment],
    ) -> list[MemoryFragment]:
        """Get memories eligible for promotion to semantic."""
        return [m for m in memories if self.should_promote(m)]
    
    def get_stats(self, memories: list[MemoryFragment]) -> dict[str, Any]:
        """Get statistics about memory weights."""
        if not memories:
            return {}
        
        weights = [m.weight for m in memories]
        return {
            "count": len(memories),
            "avg_weight": sum(weights) / len(weights),
            "min_weight": min(weights),
            "max_weight": max(weights),
            "promotion_candidates": len([m for m in memories if self.should_promote(m)]),
            "prune_candidates": len([m for m in memories if self.should_prune(m)]),
            "by_type": {
                t.value: len([m for m in memories if m.type == t])
                for t in MemoryType
            },
        }


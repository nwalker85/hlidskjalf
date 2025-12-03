"""
Hel Promoter - Memory promotion from episodic to semantic

Handles the elevation of episodic memories that have proven
their worth through reinforcement and repeated reference.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.memory.muninn.store import MuninnStore, MemoryFragment, MemoryType
from src.memory.muninn.semantic import SemanticMemory, Pattern
from src.memory.hel.weight_engine import HelWeightEngine

logger = logging.getLogger(__name__)


class HelPromoter:
    """
    Promotes episodic memories to semantic patterns.
    
    The promotion process:
    1. Identify candidates (high weight, multiple references)
    2. Extract patterns from similar episodes
    3. Create semantic pattern with evidence
    4. Optionally archive or mark promoted episodes
    """
    
    def __init__(
        self,
        store: MuninnStore,
        semantic: SemanticMemory,
        weight_engine: HelWeightEngine | None = None,
        archive_promoted: bool = True,
    ):
        self.store = store
        self.semantic = semantic
        self.weight_engine = weight_engine or HelWeightEngine()
        self.archive_promoted = archive_promoted
    
    async def promote_memory(
        self,
        memory_id: str,
        pattern_type: str = "learned",
        additional_context: dict[str, Any] | None = None,
    ) -> Pattern | None:
        """
        Promote a single episodic memory to semantic.
        
        Creates a Pattern from the episodic memory.
        """
        memory = await self.store.get(memory_id)
        if not memory:
            logger.warning(f"Memory {memory_id} not found for promotion")
            return None
        
        if memory.type != MemoryType.EPISODIC:
            logger.warning(f"Memory {memory_id} is not episodic, cannot promote")
            return None
        
        # Create pattern from memory
        pattern = Pattern(
            pattern_type=pattern_type,
            description=memory.content,
            confidence=memory.weight,
            evidence_count=memory.references,
            source_episodes=[memory_id],
            domain=memory.domain,
            scope="user" if memory.user_id else "global",
            conditions=memory.features.get("conditions", {}),
            outcomes=memory.features.get("outcomes", {}),
            tags=memory.features.get("tags", []),
        )
        
        # Add to semantic memory
        await self.semantic.add_pattern(pattern)
        
        # Mark original as promoted
        if self.archive_promoted:
            memory.features["promoted_to"] = pattern.id
            memory.features["promoted_at"] = datetime.now(timezone.utc).isoformat()
            await self.store.remember(memory)
        
        logger.info(f"Hel promoted memory {memory_id} to pattern {pattern.id}")
        return pattern
    
    async def promote_cluster(
        self,
        memory_ids: list[str],
        pattern_description: str,
        pattern_type: str = "correlation",
        conditions: dict[str, Any] | None = None,
        outcomes: dict[str, Any] | None = None,
    ) -> Pattern | None:
        """
        Promote a cluster of related episodes to a single pattern.
        
        Used when multiple episodes share a common pattern.
        """
        if not memory_ids:
            return None
        
        # Load all memories
        memories = []
        for mid in memory_ids:
            memory = await self.store.get(mid)
            if memory and memory.type == MemoryType.EPISODIC:
                memories.append(memory)
        
        if not memories:
            logger.warning("No valid episodic memories found in cluster")
            return None
        
        # Calculate aggregate confidence
        avg_weight = sum(m.weight for m in memories) / len(memories)
        total_refs = sum(m.references for m in memories)
        
        # Determine domain (most common)
        domain_counts: dict[str, int] = {}
        for m in memories:
            domain_counts[m.domain] = domain_counts.get(m.domain, 0) + 1
        domain = max(domain_counts, key=domain_counts.get)
        
        # Collect all tags
        all_tags = set()
        for m in memories:
            all_tags.update(m.features.get("tags", []))
        
        # Create the consolidated pattern
        pattern = Pattern(
            pattern_type=pattern_type,
            description=pattern_description,
            confidence=avg_weight,
            evidence_count=total_refs,
            source_episodes=memory_ids,
            domain=domain,
            scope="global",
            conditions=conditions or {},
            outcomes=outcomes or {},
            tags=list(all_tags),
        )
        
        await self.semantic.add_pattern(pattern)
        
        # Mark all originals as promoted
        if self.archive_promoted:
            for memory in memories:
                memory.features["promoted_to"] = pattern.id
                memory.features["promoted_at"] = datetime.now(timezone.utc).isoformat()
                await self.store.remember(memory)
        
        logger.info(
            f"Hel promoted cluster of {len(memories)} memories to pattern {pattern.id}"
        )
        return pattern
    
    async def auto_promote_candidates(self) -> list[Pattern]:
        """
        Automatically promote all eligible candidates.
        
        Returns list of created patterns.
        """
        promoted = []
        
        # Get candidates from database
        pool = await self.store._get_pool()
        if not pool:
            return promoted
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id FROM muninn_memories
                    WHERE type = 'episodic'
                    AND weight >= 0.8
                    AND references >= 3
                    AND NOT (features ? 'promoted_to')
                    ORDER BY weight DESC
                    LIMIT 100
                """)
                
                for row in rows:
                    pattern = await self.promote_memory(row["id"])
                    if pattern:
                        promoted.append(pattern)
                        
        except Exception as e:
            logger.error(f"Auto-promotion failed: {e}")
        
        logger.info(f"Auto-promoted {len(promoted)} memories to patterns")
        return promoted
    
    async def find_similar_episodes(
        self,
        memory_id: str,
        min_similarity: float = 0.8,
        limit: int = 10,
    ) -> list[MemoryFragment]:
        """
        Find episodes similar to a given memory.
        
        Useful for identifying clusters to promote together.
        """
        memory = await self.store.get(memory_id)
        if not memory:
            return []
        
        # Search for similar memories
        similar = await self.store.recall(
            query=memory.content,
            k=limit + 1,  # +1 to exclude self
            memory_type=MemoryType.EPISODIC,
            domain=memory.domain,
        )
        
        # Filter out self and by similarity threshold
        return [
            m for m in similar
            if m.id != memory_id and m.weight >= min_similarity * memory.weight
        ]
    
    async def suggest_promotion_clusters(
        self,
        domain: str | None = None,
        min_cluster_size: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Suggest clusters of episodes that could be promoted together.
        
        Uses simple content-based clustering.
        """
        # Get promotion candidates
        pool = await self.store._get_pool()
        if not pool:
            return []
        
        suggestions = []
        
        try:
            async with pool.acquire() as conn:
                # Get high-weight episodic memories
                where = "type = 'episodic' AND weight >= 0.6"
                if domain:
                    where += f" AND domain = '{domain}'"
                
                rows = await conn.fetch(f"""
                    SELECT id, content, domain, topic
                    FROM muninn_memories
                    WHERE {where}
                    ORDER BY weight DESC
                    LIMIT 50
                """)
                
                # Simple topic-based clustering
                topic_clusters: dict[str, list[str]] = {}
                for row in rows:
                    topic = row["topic"] or "unknown"
                    if topic not in topic_clusters:
                        topic_clusters[topic] = []
                    topic_clusters[topic].append(row["id"])
                
                # Return clusters above minimum size
                for topic, ids in topic_clusters.items():
                    if len(ids) >= min_cluster_size:
                        suggestions.append({
                            "topic": topic,
                            "memory_ids": ids,
                            "count": len(ids),
                            "suggested_pattern_type": "topic_correlation",
                        })
                        
        except Exception as e:
            logger.error(f"Cluster suggestion failed: {e}")
        
        return suggestions


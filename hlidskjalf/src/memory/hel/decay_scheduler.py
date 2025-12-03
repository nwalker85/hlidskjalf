"""
Hel Decay Scheduler - Periodic memory maintenance

Runs background jobs to:
- Apply decay to all memories
- Prune low-weight memories
- Identify promotion candidates
- Emit events for analysis
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from src.memory.muninn.store import MuninnStore, MemoryFragment, MemoryType
from src.memory.hel.weight_engine import HelWeightEngine

logger = logging.getLogger(__name__)


class HelDecayScheduler:
    """
    Periodic decay and maintenance scheduler.
    
    Runs on configurable intervals to:
    - Apply time-based decay
    - Prune forgotten memories
    - Emit events for promotions
    """
    
    def __init__(
        self,
        store: MuninnStore,
        weight_engine: HelWeightEngine | None = None,
        decay_interval_seconds: int = 3600,  # 1 hour
        prune_interval_seconds: int = 86400,  # 24 hours
        kafka_bootstrap: str | None = None,
    ):
        self.store = store
        self.weight_engine = weight_engine or HelWeightEngine()
        self.decay_interval = decay_interval_seconds
        self.prune_interval = prune_interval_seconds
        self.kafka_bootstrap = kafka_bootstrap
        
        self._decay_task: asyncio.Task | None = None
        self._prune_task: asyncio.Task | None = None
        self._running = False
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
                logger.warning("aiokafka not installed")
        return self._kafka_producer
    
    async def start(self) -> None:
        """Start the scheduler"""
        if self._running:
            return
        
        self._running = True
        self._decay_task = asyncio.create_task(self._decay_loop())
        self._prune_task = asyncio.create_task(self._prune_loop())
        
        logger.info("Hel decay scheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler"""
        self._running = False
        
        if self._decay_task:
            self._decay_task.cancel()
            try:
                await self._decay_task
            except asyncio.CancelledError:
                pass
        
        if self._prune_task:
            self._prune_task.cancel()
            try:
                await self._prune_task
            except asyncio.CancelledError:
                pass
        
        if self._kafka_producer:
            await self._kafka_producer.stop()
        
        logger.info("Hel decay scheduler stopped")
    
    async def _decay_loop(self) -> None:
        """Periodic decay loop"""
        while self._running:
            try:
                await asyncio.sleep(self.decay_interval)
                await self.run_decay_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Decay cycle failed: {e}")
    
    async def _prune_loop(self) -> None:
        """Periodic prune loop"""
        while self._running:
            try:
                await asyncio.sleep(self.prune_interval)
                await self.run_prune_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Prune cycle failed: {e}")
    
    async def run_decay_cycle(self) -> dict[str, Any]:
        """
        Run a single decay cycle.
        
        Returns statistics about the cycle.
        """
        logger.info("Hel running decay cycle")
        
        stats = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "memories_processed": 0,
            "promotion_candidates": 0,
            "prune_candidates": 0,
        }
        
        # Get all memories from database
        pool = await self.store._get_pool()
        if not pool:
            logger.warning("No database pool, skipping decay")
            return stats
        
        try:
            async with pool.acquire() as conn:
                # Apply decay using SQL for efficiency
                result = await conn.execute("""
                    UPDATE muninn_memories
                    SET weight = weight * exp(-0.001 * EXTRACT(EPOCH FROM (NOW() - last_used)) / 3600)
                    WHERE weight > 0.01
                    RETURNING id
                """)
                stats["memories_processed"] = int(result.split()[-1])
                
                # Count promotion candidates
                promo_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM muninn_memories
                    WHERE type = 'episodic'
                    AND weight >= 0.8
                    AND references >= 3
                """)
                stats["promotion_candidates"] = promo_count or 0
                
                # Count prune candidates
                prune_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM muninn_memories
                    WHERE weight < 0.1
                    AND EXTRACT(EPOCH FROM (NOW() - last_used)) / 3600 > 24
                """)
                stats["prune_candidates"] = prune_count or 0
                
        except Exception as e:
            logger.error(f"Decay cycle database error: {e}")
        
        stats["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        # Emit stats to Kafka
        await self._emit_cycle_stats("hel.decay.completed", stats)
        
        logger.info(f"Hel decay cycle completed: {stats}")
        return stats
    
    async def run_prune_cycle(self) -> dict[str, Any]:
        """
        Run a single prune cycle.
        
        Deletes memories that have decayed below threshold.
        """
        logger.info("Hel running prune cycle")
        
        stats = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "memories_pruned": 0,
            "freed_ids": [],
        }
        
        pool = await self.store._get_pool()
        if not pool:
            return stats
        
        try:
            async with pool.acquire() as conn:
                # Delete low-weight old memories
                rows = await conn.fetch("""
                    DELETE FROM muninn_memories
                    WHERE weight < 0.1
                    AND EXTRACT(EPOCH FROM (NOW() - last_used)) / 3600 > 24
                    RETURNING id
                """)
                
                stats["memories_pruned"] = len(rows)
                stats["freed_ids"] = [row["id"] for row in rows]
                
                # Emit pruned event for each
                for row in rows:
                    await self._emit_memory_event("hel.memory.forgotten", {
                        "memory_id": row["id"],
                        "reason": "decay_threshold",
                    })
                    
        except Exception as e:
            logger.error(f"Prune cycle database error: {e}")
        
        stats["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        await self._emit_cycle_stats("hel.prune.completed", stats)
        
        logger.info(f"Hel prune cycle completed: pruned {stats['memories_pruned']} memories")
        return stats
    
    async def run_promotion_check(self) -> list[str]:
        """
        Check for promotion candidates and emit events.
        
        Returns list of memory IDs that should be promoted.
        """
        candidates = []
        
        pool = await self.store._get_pool()
        if not pool:
            return candidates
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, content, domain, features
                    FROM muninn_memories
                    WHERE type = 'episodic'
                    AND weight >= 0.8
                    AND references >= 3
                """)
                
                for row in rows:
                    candidates.append(row["id"])
                    await self._emit_memory_event("hel.memory.promotion_candidate", {
                        "memory_id": row["id"],
                        "domain": row["domain"],
                        "content_preview": row["content"][:100],
                    })
                    
        except Exception as e:
            logger.error(f"Promotion check failed: {e}")
        
        return candidates
    
    async def _emit_memory_event(self, topic: str, data: dict[str, Any]) -> None:
        """Emit a memory event to Kafka"""
        try:
            producer = await self._get_kafka()
            if producer:
                import json
                await producer.send_and_wait(
                    topic,
                    json.dumps(data).encode()
                )
        except Exception as e:
            logger.error(f"Failed to emit event: {e}")
    
    async def _emit_cycle_stats(self, topic: str, stats: dict[str, Any]) -> None:
        """Emit cycle statistics to Kafka"""
        await self._emit_memory_event(topic, stats)


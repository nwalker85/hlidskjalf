"""
Muninn Store - Long-term memory with weighted fragments

Wraps PostgresStore and provides:
- Memory fragment storage with weighting
- Semantic search via pgvector
- Integration with Hel for reinforcement/decay
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

import os

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memory in Muninn"""
    EPISODIC = "episodic"    # Raw experiences
    SEMANTIC = "semantic"    # Learned patterns
    PROCEDURAL = "procedural"  # Workflows, tool usage


class MemoryFragment(BaseModel):
    """
    A weighted memory fragment in Muninn.
    
    Weight determines importance and affects:
    - Retrieval ranking
    - Promotion/demotion decisions
    - Decay rate
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: MemoryType = MemoryType.EPISODIC
    
    # Content
    content: str
    domain: str = "general"
    topic: str | None = None
    summary: str | None = None
    
    # Embedding (for semantic search)
    embedding: list[float] | None = None
    
    # Weighting (for Hel governance)
    weight: float = 0.5  # 0.0 - 1.0
    references: int = 0
    
    # Metadata
    user_id: str | None = None
    session_id: str | None = None
    source_keys: list[str] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def age_hours(self) -> float:
        """Get age in hours since last use"""
        delta = datetime.now(timezone.utc) - self.last_used
        return delta.total_seconds() / 3600
    
    def touch(self) -> None:
        """Update last_used timestamp"""
        self.last_used = datetime.now(timezone.utc)


class MuninnStore:
    """
    Muninn remembers what has been.
    
    Long-term memory store with:
    - Weighted fragment storage
    - Semantic search via embeddings (Ollama or OpenAI)
    - User episode tracking
    - Integration with Hel for governance
    """
    
    def __init__(
        self,
        database_url: str | None = None,
        store=None,  # Optional PostgresStore instance
        embedding_model: str = "text-embedding-3-small",
        ollama_base_url: str | None = None,
        use_ollama: bool = True,  # Prefer Ollama for cost savings
    ):
        self.database_url = database_url
        self.store = store
        self.embedding_model = embedding_model
        # Prefer env override so containers can talk to host-based Ollama
        self.ollama_base_url = (
            ollama_base_url
            or os.environ.get("OLLAMA_BASE_URL")
            or "http://ollama:11434"
        )
        self.use_ollama = use_ollama
        
        # Local index for fast lookups
        self._memory_index: dict[str, MemoryFragment] = {}
        
        # Database connection (lazy init)
        self._pool = None
        self._embedder = None
        self._ollama_embedder = None
    
    async def _get_pool(self):
        """Lazy database connection pool"""
        if self._pool is None and self.database_url:
            try:
                import asyncpg
                self._pool = await asyncpg.create_pool(self.database_url)
            except ImportError:
                logger.warning("asyncpg not installed, database disabled")
        return self._pool
    
    async def _get_embedder(self):
        """Lazy embedding model - prefers Ollama for cost savings"""
        # Try Ollama first if enabled
        if self.use_ollama and self._ollama_embedder is None:
            try:
                from src.memory.ollama_provider import OllamaEmbeddingsLC
                self._ollama_embedder = OllamaEmbeddingsLC(
                    base_url=self.ollama_base_url,
                    model="nomic-embed-text",
                )
                # Test connection (async method)
                test_emb = await self._ollama_embedder.aembed_query("test")
                if test_emb:
                    logger.info("Using Ollama for embeddings (nomic-embed-text)")
                    return self._ollama_embedder
            except Exception as e:
                logger.debug(f"Ollama embeddings not available: {e}")
                self._ollama_embedder = None
        
        if self._ollama_embedder:
            return self._ollama_embedder
        
        # Fall back to OpenAI
        if self._embedder is None:
            try:
                from langchain_openai import OpenAIEmbeddings
                self._embedder = OpenAIEmbeddings(model=self.embedding_model)
                logger.info(f"Using OpenAI for embeddings ({self.embedding_model})")
            except ImportError:
                logger.warning("langchain_openai not installed, embeddings disabled")
        return self._embedder
    
    async def remember(self, fragment: MemoryFragment) -> str:
        """
        Store a memory fragment.
        
        Returns the fragment ID.
        """
        # Generate embedding if not provided
        if fragment.embedding is None:
            embedder = await self._get_embedder()
            if embedder:
                try:
                    fragment.embedding = await embedder.aembed_query(fragment.content)
                except Exception as e:
                    logger.error(f"Failed to generate embedding: {e}")
        
        # Store in local index
        self._memory_index[fragment.id] = fragment
        
        # Persist to database
        pool = await self._get_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO muninn_memories (
                            id, type, content, domain, topic, summary,
                            embedding, weight, references, user_id, session_id,
                            features, created_at, last_used
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            weight = EXCLUDED.weight,
                            references = EXCLUDED.references,
                            last_used = EXCLUDED.last_used
                    """,
                        fragment.id,
                        fragment.type.value,
                        fragment.content,
                        fragment.domain,
                        fragment.topic,
                        fragment.summary,
                        fragment.embedding,
                        fragment.weight,
                        fragment.references,
                        fragment.user_id,
                        fragment.session_id,
                        fragment.features,
                        fragment.created_at,
                        fragment.last_used,
                    )
            except Exception as e:
                logger.error(f"Failed to persist memory: {e}")
        
        # Also store in PostgresStore if available
        if self.store:
            try:
                namespace = ("muninn", fragment.type.value)
                await self.store.aput(namespace, fragment.id, fragment.model_dump())
            except Exception as e:
                logger.error(f"Failed to store in PostgresStore: {e}")
        
        logger.debug(f"Muninn remembered: {fragment.id}")
        return fragment.id
    
    async def recall(
        self, 
        query: str, 
        k: int = 5,
        memory_type: MemoryType | None = None,
        domain: str | None = None,
        min_weight: float = 0.0,
    ) -> list[MemoryFragment]:
        """
        Semantic search over memories.
        
        Returns top-k memories ordered by relevance and weight.
        """
        # Generate query embedding
        embedder = await self._get_embedder()
        if not embedder:
            # Fall back to local index search
            logger.debug("recall: no embedder, falling back to keyword search")
            return self._local_search(query, k, memory_type, domain, min_weight)
        
        try:
            query_embedding = await embedder.aembed_query(query)
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            return self._local_search(query, k, memory_type, domain, min_weight)
        
        # Search database with pgvector if available
        pool = await self._get_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    # Build query with filters
                    where_clauses = ["weight >= $2"]
                    params = [query_embedding, min_weight]
                    param_idx = 3
                    
                    if memory_type:
                        where_clauses.append(f"type = ${param_idx}")
                        params.append(memory_type.value)
                        param_idx += 1
                    
                    if domain:
                        where_clauses.append(f"domain = ${param_idx}")
                        params.append(domain)
                        param_idx += 1
                    
                    where_sql = " AND ".join(where_clauses)
                    
                    rows = await conn.fetch(f"""
                        SELECT *, 
                            1 - (embedding <=> $1::vector) as similarity
                        FROM muninn_memories
                        WHERE {where_sql}
                        ORDER BY (weight * 0.3 + (1 - (embedding <=> $1::vector)) * 0.7) DESC
                        LIMIT {k}
                    """, *params)
                    
                    return [self._row_to_fragment(row) for row in rows]
                    
            except Exception as e:
                logger.error(f"Failed to search memories: {e}")
        
        # Fall back to embedding-based search on local index
        return self._local_embedding_search(query_embedding, k, memory_type, domain, min_weight)
    
    def _local_search(
        self,
        query: str,
        k: int,
        memory_type: MemoryType | None,
        domain: str | None,
        min_weight: float,
    ) -> list[MemoryFragment]:
        """Fall back to local keyword search"""
        query_lower = query.lower()
        matches = []
        
        for fragment in self._memory_index.values():
            # Apply filters
            if fragment.weight < min_weight:
                continue
            if memory_type and fragment.type != memory_type:
                continue
            if domain and fragment.domain != domain:
                continue
            
            # Simple keyword matching
            if query_lower in fragment.content.lower():
                matches.append(fragment)
        
        # Sort by weight
        matches.sort(key=lambda m: m.weight, reverse=True)
        return matches[:k]
    
    def _local_embedding_search(
        self,
        query_embedding: list[float],
        k: int,
        memory_type: MemoryType | None,
        domain: str | None,
        min_weight: float,
    ) -> list[MemoryFragment]:
        """Semantic search on local index using cosine similarity"""
        import numpy as np
        
        matches = []
        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)
        
        if query_norm == 0:
            logger.warning("Query embedding is zero vector, falling back to keyword search")
            return []
        
        query_vec_normalized = query_vec / query_norm
        
        for fragment in self._memory_index.values():
            # Apply filters
            if fragment.weight < min_weight:
                continue
            if memory_type and fragment.type != memory_type:
                continue
            if domain and fragment.domain != domain:
                continue
            
            # Skip if no embedding
            if not fragment.embedding:
                continue
            
            # Compute cosine similarity
            frag_vec = np.array(fragment.embedding)
            frag_norm = np.linalg.norm(frag_vec)
            if frag_norm == 0:
                continue
            
            frag_vec_normalized = frag_vec / frag_norm
            similarity = float(np.dot(query_vec_normalized, frag_vec_normalized))
            
            # Combine similarity with weight (30% weight, 70% similarity)
            score = fragment.weight * 0.3 + similarity * 0.7
            matches.append((score, fragment))
        
        # Sort by combined score
        matches.sort(key=lambda x: x[0], reverse=True)
        
        logger.info(f"Local embedding search: found {len(matches)} candidates")
        
        return [m[1] for m in matches[:k]]
    
    def _row_to_fragment(self, row) -> MemoryFragment:
        """Convert database row to MemoryFragment"""
        return MemoryFragment(
            id=row["id"],
            type=MemoryType(row["type"]),
            content=row["content"],
            domain=row["domain"],
            topic=row["topic"],
            summary=row["summary"],
            embedding=list(row["embedding"]) if row["embedding"] else None,
            weight=row["weight"],
            references=row["references"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            features=row["features"] or {},
            created_at=row["created_at"],
            last_used=row["last_used"],
        )
    
    async def get(self, memory_id: str) -> MemoryFragment | None:
        """Get a specific memory by ID"""
        # Check local index first
        if memory_id in self._memory_index:
            return self._memory_index[memory_id]
        
        # Check database
        pool = await self._get_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM muninn_memories WHERE id = $1",
                        memory_id
                    )
                    if row:
                        fragment = self._row_to_fragment(row)
                        self._memory_index[memory_id] = fragment
                        return fragment
            except Exception as e:
                logger.error(f"Failed to get memory: {e}")
        
        return None
    
    async def get_user_episodes(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> list[MemoryFragment]:
        """Get recent episodes for a user"""
        pool = await self._get_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT * FROM muninn_memories
                        WHERE user_id = $1 AND type = 'episodic'
                        ORDER BY created_at DESC
                        LIMIT $2
                    """, user_id, limit)
                    return [self._row_to_fragment(row) for row in rows]
            except Exception as e:
                logger.error(f"Failed to get user episodes: {e}")
        
        # Fall back to local index
        episodes = [
            f for f in self._memory_index.values()
            if f.user_id == user_id and f.type == MemoryType.EPISODIC
        ]
        episodes.sort(key=lambda e: e.created_at, reverse=True)
        return episodes[:limit]
    
    async def update_weight(self, memory_id: str, new_weight: float) -> bool:
        """Update memory weight (used by Hel)"""
        fragment = await self.get(memory_id)
        if not fragment:
            return False
        
        fragment.weight = max(0.0, min(1.0, new_weight))
        
        pool = await self._get_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE muninn_memories SET weight = $1 WHERE id = $2",
                        fragment.weight, memory_id
                    )
            except Exception as e:
                logger.error(f"Failed to update weight: {e}")
        
        return True
    
    async def forget(self, memory_id: str) -> bool:
        """Remove a memory (used by Hel for pruning)"""
        self._memory_index.pop(memory_id, None)
        
        pool = await self._get_pool()
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM muninn_memories WHERE id = $1",
                        memory_id
                    )
                    return True
            except Exception as e:
                logger.error(f"Failed to delete memory: {e}")
        
        return False
    
    async def close(self) -> None:
        """Clean up connections"""
        if self._pool:
            await self._pool.close()


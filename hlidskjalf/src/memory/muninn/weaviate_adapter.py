"""
Weaviate Adapter - Production RAG with hybrid search

Syncs Muninn memories to Weaviate for:
- Semantic search via embeddings
- Keyword search (BM25)
- Hybrid search with reranking
- Production-scale vector operations

Leverages the ai-infra stack:
- Weaviate (port 8084): Vector database
- Embeddings (port 8085): sentence-transformers/all-MiniLM-L6-v2
- Reranker (port 8086): BAAI/bge-reranker-base
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class WeaviateAdapter:
    """
    Adapter for syncing Muninn memories to Weaviate.
    
    Features:
    - Automatic schema management
    - Batch operations for efficiency
    - Hybrid search (semantic + keyword)
    - Reranking for precision
    """
    
    def __init__(
        self,
        weaviate_url: str = "http://weaviate:8084",
        embedding_url: str = "http://embeddings:8085",
        reranker_url: str = "http://reranker:8086",
    ):
        self.weaviate_url = weaviate_url
        self.embedding_url = embedding_url
        self.reranker_url = reranker_url
        self._client = None
    
    async def _get_client(self):
        """Lazy Weaviate client initialization."""
        if self._client is None:
            try:
                import weaviate
                from weaviate.classes.init import Auth
                
                self._client = weaviate.connect_to_custom(
                    http_host=self.weaviate_url.replace("http://", "").split(":")[0],
                    http_port=int(self.weaviate_url.split(":")[-1]),
                    http_secure=False,
                    grpc_host=self.weaviate_url.replace("http://", "").split(":")[0],
                    grpc_port=50051,
                    grpc_secure=False,
                )
                
                logger.info(f"Connected to Weaviate at {self.weaviate_url}")
            except ImportError:
                logger.warning("weaviate-client not installed")
                return None
            except Exception as e:
                logger.error(f"Failed to connect to Weaviate: {e}")
                return None
        
        return self._client
    
    async def ensure_schema(self) -> bool:
        """
        Ensure Weaviate schema exists for Muninn memories.
        
        Creates classes:
        - ProceduralMemory (skills, workflows)
        - SemanticMemory (documents, facts)
        - EpisodicMemory (interactions, events)
        """
        client = await self._get_client()
        if not client:
            return False
        
        try:
            from weaviate.classes.config import Configure, Property, DataType
            
            # ProceduralMemory class (skills)
            if not client.collections.exists("ProceduralMemory"):
                client.collections.create(
                    name="ProceduralMemory",
                    vectorizer_config=Configure.Vectorizer.text2vec_transformers(
                        vectorize_collection_name=False
                    ),
                    properties=[
                        Property(name="memory_id", data_type=DataType.TEXT),
                        Property(name="name", data_type=DataType.TEXT),
                        Property(name="content", data_type=DataType.TEXT),
                        Property(name="summary", data_type=DataType.TEXT),
                        Property(name="domain", data_type=DataType.TEXT),
                        Property(name="topic", data_type=DataType.TEXT),
                        Property(name="roles", data_type=DataType.TEXT_ARRAY),
                        Property(name="tags", data_type=DataType.TEXT_ARRAY),
                        Property(name="weight", data_type=DataType.NUMBER),
                        Property(name="references", data_type=DataType.INT),
                    ],
                )
                logger.info("Created ProceduralMemory class in Weaviate")
            
            # SemanticMemory class (documents)
            if not client.collections.exists("SemanticMemory"):
                client.collections.create(
                    name="SemanticMemory",
                    vectorizer_config=Configure.Vectorizer.text2vec_transformers(
                        vectorize_collection_name=False
                    ),
                    properties=[
                        Property(name="memory_id", data_type=DataType.TEXT),
                        Property(name="content", data_type=DataType.TEXT),
                        Property(name="summary", data_type=DataType.TEXT),
                        Property(name="domain", data_type=DataType.TEXT),
                        Property(name="topic", data_type=DataType.TEXT),
                        Property(name="source_url", data_type=DataType.TEXT),
                        Property(name="weight", data_type=DataType.NUMBER),
                    ],
                )
                logger.info("Created SemanticMemory class in Weaviate")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create Weaviate schema: {e}")
            return False
    
    async def sync_procedural(
        self,
        memories: list,
    ) -> int:
        """
        Sync procedural memories (skills) to Weaviate.
        
        Args:
            memories: List of MemoryFragment objects with type=PROCEDURAL
            
        Returns:
            Number of memories synced
        """
        client = await self._get_client()
        if not client:
            return 0
        
        await self.ensure_schema()
        
        try:
            collection = client.collections.get("ProceduralMemory")
            synced = 0
            
            # Batch insert for efficiency
            with collection.batch.dynamic() as batch:
                for mem in memories:
                    if mem.topic != "skill":
                        continue
                    
                    # Prepare data object
                    data_obj = {
                        "memory_id": mem.id,
                        "name": mem.features.get("name", ""),
                        "content": mem.content,
                        "summary": mem.summary or "",
                        "domain": mem.domain,
                        "topic": mem.topic or "",
                        "roles": mem.features.get("roles", []),
                        "tags": mem.features.get("tags", []),
                        "weight": mem.weight,
                        "references": mem.references,
                    }
                    
                    batch.add_object(
                        properties=data_obj,
                        uuid=mem.id,
                    )
                    synced += 1
            
            logger.info(f"Synced {synced} procedural memories to Weaviate")
            return synced
            
        except Exception as e:
            logger.error(f"Failed to sync procedural memories: {e}")
            return 0
    
    async def sync_semantic(
        self,
        memories: list,
    ) -> int:
        """
        Sync semantic memories (documents) to Weaviate.
        
        Args:
            memories: List of MemoryFragment objects with type=SEMANTIC
            
        Returns:
            Number of memories synced
        """
        client = await self._get_client()
        if not client:
            return 0
        
        await self.ensure_schema()
        
        try:
            collection = client.collections.get("SemanticMemory")
            synced = 0
            
            with collection.batch.dynamic() as batch:
                for mem in memories:
                    data_obj = {
                        "memory_id": mem.id,
                        "content": mem.content,
                        "summary": mem.summary or "",
                        "domain": mem.domain,
                        "topic": mem.topic or "",
                        "source_url": mem.features.get("source_url", ""),
                        "weight": mem.weight,
                    }
                    
                    batch.add_object(
                        properties=data_obj,
                        uuid=mem.id,
                    )
                    synced += 1
            
            logger.info(f"Synced {synced} semantic memories to Weaviate")
            return synced
            
        except Exception as e:
            logger.error(f"Failed to sync semantic memories: {e}")
            return 0
    
    async def hybrid_search(
        self,
        query: str,
        collection_name: str = "ProceduralMemory",
        filters: dict[str, Any] | None = None,
        limit: int = 10,
        alpha: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Hybrid search combining semantic and keyword search.
        
        Args:
            query: Search query
            collection_name: Weaviate collection to search
            filters: Optional filters (e.g., {"domain": "ravenhelm"})
            limit: Number of results
            alpha: Hybrid search weight (0=keyword, 1=semantic, 0.5=balanced)
            
        Returns:
            List of matching objects with metadata
        """
        client = await self._get_client()
        if not client:
            return []
        
        try:
            collection = client.collections.get(collection_name)
            
            # Build filter
            from weaviate.classes.query import Filter
            weaviate_filter = None
            if filters:
                if "domain" in filters:
                    weaviate_filter = Filter.by_property("domain").equal(filters["domain"])
                if "roles" in filters and "roles" in filters:
                    role_filter = Filter.by_property("roles").contains_any(filters["roles"])
                    weaviate_filter = weaviate_filter & role_filter if weaviate_filter else role_filter
            
            # Hybrid search
            response = collection.query.hybrid(
                query=query,
                alpha=alpha,
                limit=limit,
                filters=weaviate_filter,
                return_metadata=["score", "distance"],
            )
            
            results = []
            for obj in response.objects:
                results.append({
                    "id": str(obj.uuid),
                    "memory_id": obj.properties.get("memory_id"),
                    "name": obj.properties.get("name", ""),
                    "content": obj.properties.get("content", ""),
                    "summary": obj.properties.get("summary", ""),
                    "domain": obj.properties.get("domain", ""),
                    "weight": obj.properties.get("weight", 0.0),
                    "score": obj.metadata.score if obj.metadata else None,
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []
    
    async def semantic_search(
        self,
        query: str,
        collection_name: str = "ProceduralMemory",
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Pure semantic search using vector similarity."""
        return await self.hybrid_search(
            query=query,
            collection_name=collection_name,
            filters=filters,
            limit=limit,
            alpha=1.0,  # Pure semantic
        )
    
    async def keyword_search(
        self,
        query: str,
        collection_name: str = "ProceduralMemory",
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Pure keyword search using BM25."""
        return await self.hybrid_search(
            query=query,
            collection_name=collection_name,
            filters=filters,
            limit=limit,
            alpha=0.0,  # Pure keyword
        )
    
    async def delete_memory(
        self,
        memory_id: str,
        collection_name: str = "ProceduralMemory",
    ) -> bool:
        """Delete a memory from Weaviate."""
        client = await self._get_client()
        if not client:
            return False
        
        try:
            collection = client.collections.get(collection_name)
            collection.data.delete_by_id(memory_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory: {e}")
            return False
    
    async def get_stats(self) -> dict[str, Any]:
        """Get Weaviate statistics."""
        client = await self._get_client()
        if not client:
            return {}
        
        try:
            stats = {
                "procedural_count": 0,
                "semantic_count": 0,
            }
            
            if client.collections.exists("ProceduralMemory"):
                proc = client.collections.get("ProceduralMemory")
                stats["procedural_count"] = proc.aggregate.over_all(total_count=True).total_count
            
            if client.collections.exists("SemanticMemory"):
                sem = client.collections.get("SemanticMemory")
                stats["semantic_count"] = sem.aggregate.over_all(total_count=True).total_count
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
    
    async def close(self) -> None:
        """Close Weaviate connection."""
        if self._client:
            self._client.close()


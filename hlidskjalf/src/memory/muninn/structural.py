"""
Structural Memory - Knowledge Graph

Uses Neo4j for domain ontology and entity relationships.
Uses Memgraph for hot-path graph queries.

Synced from Mímir's DIS dossiers.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GraphNode(BaseModel):
    """A node in the knowledge graph"""
    node_id: str
    node_type: str  # "entity", "role", "concept", "action"
    name: str
    properties: dict[str, Any] = {}


class GraphEdge(BaseModel):
    """An edge in the knowledge graph"""
    edge_id: str
    edge_type: str  # "HAS_ROLE", "RELATES_TO", "ACTS_ON", etc.
    source_id: str
    target_id: str
    properties: dict[str, Any] = {}


class StructuralMemory:
    """
    Knowledge graph backed by Neo4j and Memgraph.
    
    Features:
    - Domain ontology storage
    - Entity relationship tracking
    - Graph traversal queries
    - Hot-path queries via Memgraph
    """
    
    def __init__(
        self,
        neo4j_uri: str | None = None,
        neo4j_auth: tuple[str, str] | None = None,
        memgraph_uri: str | None = None,
    ):
        self.neo4j_uri = neo4j_uri
        self.neo4j_auth = neo4j_auth
        self.memgraph_uri = memgraph_uri
        
        self._neo4j_driver = None
        self._memgraph_driver = None
    
    async def _get_neo4j(self):
        """Lazy Neo4j connection"""
        if self._neo4j_driver is None and self.neo4j_uri:
            try:
                from neo4j import AsyncGraphDatabase
                self._neo4j_driver = AsyncGraphDatabase.driver(
                    self.neo4j_uri,
                    auth=self.neo4j_auth,
                )
            except ImportError:
                logger.warning("neo4j not installed")
        return self._neo4j_driver
    
    async def _get_memgraph(self):
        """Lazy Memgraph connection"""
        if self._memgraph_driver is None and self.memgraph_uri:
            try:
                from neo4j import AsyncGraphDatabase
                self._memgraph_driver = AsyncGraphDatabase.driver(
                    self.memgraph_uri,
                )
            except ImportError:
                logger.warning("neo4j driver not installed (used for Memgraph)")
        return self._memgraph_driver
    
    async def add_node(self, node: GraphNode, use_memgraph: bool = False) -> bool:
        """Add a node to the graph"""
        driver = await (self._get_memgraph() if use_memgraph else self._get_neo4j())
        if not driver:
            return False
        
        try:
            async with driver.session() as session:
                await session.run(
                    f"""
                    MERGE (n:{node.node_type} {{id: $id}})
                    SET n.name = $name, n += $props
                    """,
                    id=node.node_id,
                    name=node.name,
                    props=node.properties,
                )
            return True
        except Exception as e:
            logger.error(f"Failed to add node: {e}")
            return False
    
    async def add_edge(self, edge: GraphEdge, use_memgraph: bool = False) -> bool:
        """Add an edge to the graph"""
        driver = await (self._get_memgraph() if use_memgraph else self._get_neo4j())
        if not driver:
            return False
        
        try:
            async with driver.session() as session:
                await session.run(
                    f"""
                    MATCH (s {{id: $source}})
                    MATCH (t {{id: $target}})
                    MERGE (s)-[r:{edge.edge_type} {{id: $edge_id}}]->(t)
                    SET r += $props
                    """,
                    source=edge.source_id,
                    target=edge.target_id,
                    edge_id=edge.edge_id,
                    props=edge.properties,
                )
            return True
        except Exception as e:
            logger.error(f"Failed to add edge: {e}")
            return False
    
    async def query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
        use_memgraph: bool = False,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query"""
        driver = await (self._get_memgraph() if use_memgraph else self._get_neo4j())
        if not driver:
            return []
        
        try:
            async with driver.session() as session:
                result = await session.run(cypher, params or {})
                records = await result.data()
                return records
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    async def get_neighbors(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "both",
        use_memgraph: bool = True,  # Hot-path, use Memgraph
    ) -> list[GraphNode]:
        """Get neighboring nodes"""
        if direction == "outgoing":
            pattern = "(n {id: $id})-[r]->(m)"
        elif direction == "incoming":
            pattern = "(n {id: $id})<-[r]-(m)"
        else:
            pattern = "(n {id: $id})-[r]-(m)"
        
        if edge_type:
            pattern = pattern.replace("[r]", f"[r:{edge_type}]")
        
        cypher = f"""
            MATCH {pattern}
            RETURN m.id as id, labels(m)[0] as type, m.name as name, m as props
        """
        
        results = await self.query(cypher, {"id": node_id}, use_memgraph=use_memgraph)
        
        return [
            GraphNode(
                node_id=r["id"],
                node_type=r["type"],
                name=r["name"],
                properties=dict(r["props"]) if r["props"] else {},
            )
            for r in results
        ]
    
    async def find_path(
        self,
        start_id: str,
        end_id: str,
        max_hops: int = 5,
        use_memgraph: bool = True,
    ) -> list[dict[str, Any]]:
        """Find shortest path between two nodes"""
        cypher = f"""
            MATCH path = shortestPath(
                (s {{id: $start}})-[*..{max_hops}]-(e {{id: $end}})
            )
            RETURN nodes(path) as nodes, relationships(path) as edges
        """
        
        return await self.query(
            cypher,
            {"start": start_id, "end": end_id},
            use_memgraph=use_memgraph,
        )
    
    async def get_entity_context(
        self,
        entity_id: str,
        depth: int = 2,
    ) -> dict[str, Any]:
        """Get full context for an entity (roles, relationships, etc.)"""
        cypher = """
            MATCH (e {id: $id})
            OPTIONAL MATCH (e)-[:HAS_ROLE]->(r:Role)
            OPTIONAL MATCH (e)-[rel]-(related)
            RETURN e as entity,
                   collect(DISTINCT r) as roles,
                   collect(DISTINCT {type: type(rel), node: related}) as relationships
        """
        
        results = await self.query(cypher, {"id": entity_id})
        if not results:
            return {}
        
        r = results[0]
        return {
            "entity": dict(r["entity"]) if r["entity"] else {},
            "roles": [dict(role) for role in r["roles"] if role],
            "relationships": r["relationships"],
        }
    
    async def sync_from_dossier(self, dossier: dict[str, Any]) -> None:
        """
        Sync domain knowledge from a DIS dossier.
        
        Called by Mímir when dossier is loaded.
        """
        # Sync entities
        for entity in dossier.get("entities", []):
            await self.add_node(GraphNode(
                node_id=entity["entityId"],
                node_type="Entity",
                name=entity["name"],
                properties=entity,
            ))
        
        # Sync roles
        for role in dossier.get("roles", []):
            await self.add_node(GraphNode(
                node_id=role["roleId"],
                node_type="Role",
                name=role["name"],
                properties=role,
            ))
        
        # Sync triplets as relationships
        for triplet in dossier.get("triplets", []):
            await self.add_edge(GraphEdge(
                edge_id=triplet["tripletId"],
                edge_type=triplet["modeOfInteraction"],
                source_id=triplet["actingEntityId"],
                target_id=triplet["targetEntityId"],
                properties=triplet,
            ))
        
        logger.info(f"Synced dossier to structural memory")
    
    async def close(self) -> None:
        """Clean up connections"""
        if self._neo4j_driver:
            await self._neo4j_driver.close()
        if self._memgraph_driver:
            await self._memgraph_driver.close()


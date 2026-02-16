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
    
    # =========================================================================
    # Skill Relationship Graph (Procedural Memory)
    # =========================================================================
    
    async def add_skill(
        self,
        skill_id: str,
        name: str,
        roles: list[str],
        summary: str,
        domain: str = "ravenhelm",
        weight: float = 0.5,
    ) -> bool:
        """Add a skill node to the graph."""
        node = GraphNode(
            node_id=skill_id,
            node_type="Skill",
            name=name,
            properties={
                "summary": summary,
                "domain": domain,
                "roles": roles,
                "weight": weight,
            },
        )
        return await self.add_node(node)
    
    async def add_skill_dependency(
        self,
        skill_id: str,
        required_skill_id: str,
        relationship_type: str = "REQUIRES",
    ) -> bool:
        """
        Add a dependency relationship between skills.
        
        Relationship types:
        - REQUIRES: Hard dependency (must know before using)
        - FOLLOWS: Sequential (usually done after)
        - ALTERNATIVE_TO: Can be used instead of
        - ENHANCES: Complements another skill
        """
        edge = GraphEdge(
            edge_id=f"{skill_id}_{relationship_type}_{required_skill_id}",
            edge_type=relationship_type,
            source_id=skill_id,
            target_id=required_skill_id,
            properties={},
        )
        return await self.add_edge(edge)
    
    async def add_role_skill_permission(
        self,
        role_id: str,
        skill_id: str,
    ) -> bool:
        """Add CAN_USE relationship between role and skill."""
        edge = GraphEdge(
            edge_id=f"{role_id}_CAN_USE_{skill_id}",
            edge_type="CAN_USE",
            source_id=role_id,
            target_id=skill_id,
            properties={},
        )
        return await self.add_edge(edge)
    
    async def get_skill_dependencies(
        self,
        skill_id: str,
        recursive: bool = True,
        use_memgraph: bool = True,
    ) -> list[GraphNode]:
        """
        Get all dependencies for a skill.
        
        Args:
            skill_id: Skill memory ID
            recursive: Include transitive dependencies
            use_memgraph: Use Memgraph for hot-path query
            
        Returns:
            List of required skills
        """
        if recursive:
            cypher = """
                MATCH path = (s:Skill {id: $id})-[:REQUIRES*]->(dep:Skill)
                RETURN DISTINCT dep.id as id, dep.name as name, dep as props
            """
        else:
            cypher = """
                MATCH (s:Skill {id: $id})-[:REQUIRES]->(dep:Skill)
                RETURN dep.id as id, dep.name as name, dep as props
            """
        
        results = await self.query(cypher, {"id": skill_id}, use_memgraph=use_memgraph)
        
        return [
            GraphNode(
                node_id=r["id"],
                node_type="Skill",
                name=r["name"],
                properties=dict(r["props"]) if r["props"] else {},
            )
            for r in results
        ]
    
    async def get_skills_for_role(
        self,
        role_id: str,
        include_inherited: bool = True,
        use_memgraph: bool = True,
    ) -> list[GraphNode]:
        """
        Get all skills a role can use.
        
        Args:
            role_id: Role identifier (e.g., "sre", "devops")
            include_inherited: Include skills from parent roles
            use_memgraph: Use Memgraph for hot-path query
            
        Returns:
            List of authorized skills
        """
        if include_inherited:
            # Include parent roles (e.g., SRE includes DevOps skills)
            cypher = """
                MATCH (r:Role {id: $id})
                MATCH (r)-[:CAN_USE|INCLUDES*]->(s:Skill)
                RETURN DISTINCT s.id as id, s.name as name, s as props
                ORDER BY s.weight DESC
            """
        else:
            cypher = """
                MATCH (r:Role {id: $id})-[:CAN_USE]->(s:Skill)
                RETURN s.id as id, s.name as name, s as props
                ORDER BY s.weight DESC
            """
        
        results = await self.query(cypher, {"id": role_id}, use_memgraph=use_memgraph)
        
        return [
            GraphNode(
                node_id=r["id"],
                node_type="Skill",
                name=r["name"],
                properties=dict(r["props"]) if r["props"] else {},
            )
            for r in results
        ]
    
    async def get_skill_workflow(
        self,
        start_skill_id: str,
        use_memgraph: bool = True,
    ) -> list[GraphNode]:
        """
        Get the typical workflow sequence starting from a skill.
        
        Follows FOLLOWS relationships to build a workflow chain.
        
        Returns:
            Ordered list of skills in workflow
        """
        cypher = """
            MATCH path = (s:Skill {id: $id})-[:FOLLOWS*0..10]->(next:Skill)
            WITH path, length(path) as depth
            ORDER BY depth
            UNWIND nodes(path) as skill
            RETURN DISTINCT skill.id as id, skill.name as name, skill as props
        """
        
        results = await self.query(cypher, {"id": start_skill_id}, use_memgraph=use_memgraph)
        
        return [
            GraphNode(
                node_id=r["id"],
                node_type="Skill",
                name=r["name"],
                properties=dict(r["props"]) if r["props"] else {},
            )
            for r in results
        ]
    
    async def find_alternative_skills(
        self,
        skill_id: str,
        use_memgraph: bool = True,
    ) -> list[GraphNode]:
        """
        Find alternative skills that can be used instead.
        
        Useful for suggesting alternatives when a skill fails.
        """
        cypher = """
            MATCH (s:Skill {id: $id})-[:ALTERNATIVE_TO]-(alt:Skill)
            RETURN alt.id as id, alt.name as name, alt as props
            ORDER BY alt.weight DESC
        """
        
        results = await self.query(cypher, {"id": skill_id}, use_memgraph=use_memgraph)
        
        return [
            GraphNode(
                node_id=r["id"],
                node_type="Skill",
                name=r["name"],
                properties=dict(r["props"]) if r["props"] else {},
            )
            for r in results
        ]
    
    async def sync_skills_from_procedural_memory(
        self,
        procedural_memories: list,
    ) -> int:
        """
        Sync skills from Muninn procedural memory to Neo4j graph.
        
        Args:
            procedural_memories: List of MemoryFragment objects with type=PROCEDURAL
            
        Returns:
            Number of skills synced
        """
        synced_count = 0
        
        for mem in procedural_memories:
            if mem.topic != "skill":
                continue
            
            # Add skill node
            success = await self.add_skill(
                skill_id=mem.id,
                name=mem.features.get("name", "Unknown"),
                roles=mem.features.get("roles", []),
                summary=mem.summary or "",
                domain=mem.domain,
                weight=mem.weight,
            )
            
            if not success:
                continue
            
            # Add role permissions
            for role in mem.features.get("roles", []):
                await self.add_role_skill_permission(
                    role_id=role,
                    skill_id=mem.id,
                )
            
            # Add dependencies
            for dep_name in mem.features.get("dependencies", []):
                # Find dependency by name (need to look up from memory store)
                # This is simplified - in production you'd maintain a name->id mapping
                pass
            
            synced_count += 1
        
        logger.info(f"Synced {synced_count} skills to structural memory")
        return synced_count
    
    async def close(self) -> None:
        """Clean up connections"""
        if self._neo4j_driver:
            await self._neo4j_driver.close()
        if self._memgraph_driver:
            await self._memgraph_driver.close()


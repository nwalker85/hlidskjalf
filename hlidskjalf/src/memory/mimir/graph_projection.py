"""
Mímir Graph Projection - Sync DIS dossiers to Neo4j

Projects domain intelligence into a knowledge graph for runtime queries.
"""

from __future__ import annotations

import logging
from typing import Any

from src.memory.mimir.models import DISDossier

logger = logging.getLogger(__name__)


class MimirGraphProjection:
    """
    Project Mímir's wisdom into Neo4j for runtime traversal.
    
    Creates nodes for:
    - Entities
    - Roles
    - Functions
    
    Creates relationships for:
    - Triplets (behavioral grammar)
    - Entity-Role assignments
    - Relationships from RelationshipMatrix
    """
    
    def __init__(
        self,
        neo4j_uri: str | None = None,
        neo4j_auth: tuple[str, str] | None = None,
    ):
        self.neo4j_uri = neo4j_uri
        self.neo4j_auth = neo4j_auth
        self._driver = None
    
    async def _get_driver(self):
        """Lazy Neo4j connection"""
        if self._driver is None and self.neo4j_uri:
            try:
                from neo4j import AsyncGraphDatabase
                self._driver = AsyncGraphDatabase.driver(
                    self.neo4j_uri,
                    auth=self.neo4j_auth,
                )
            except ImportError:
                logger.warning("neo4j driver not installed")
        return self._driver
    
    async def project(self, dossier: DISDossier) -> dict[str, int]:
        """
        Sync DIS dossier to Neo4j.
        
        Returns counts of created nodes and relationships.
        """
        driver = await self._get_driver()
        if not driver:
            logger.warning("No Neo4j driver, skipping projection")
            return {}
        
        stats = {
            "entities": 0,
            "roles": 0,
            "triplets": 0,
            "relationships": 0,
        }
        
        async with driver.session() as session:
            # Create constraints (idempotent)
            await self._create_constraints(session)
            
            # Project entities
            for entity in dossier.entities:
                await session.run("""
                    MERGE (e:Entity {entityId: $id})
                    SET e.name = $name,
                        e.entityType = $type,
                        e.description = $desc
                """,
                    id=entity.entityId,
                    name=entity.name,
                    type=entity.entityType.value,
                    desc=entity.description or "",
                )
                stats["entities"] += 1
            
            # Project roles
            for role in dossier.roles:
                await session.run("""
                    MERGE (r:Role {roleId: $id})
                    SET r.name = $name,
                        r.roleType = $type,
                        r.description = $desc
                """,
                    id=role.roleId,
                    name=role.name,
                    type=role.roleType.value,
                    desc=role.description or "",
                )
                stats["roles"] += 1
            
            # Project entity-role assignments
            for entity in dossier.entities:
                for role_id in entity.assignedRoleIds:
                    await session.run("""
                        MATCH (e:Entity {entityId: $eid})
                        MATCH (r:Role {roleId: $rid})
                        MERGE (e)-[:HAS_ROLE]->(r)
                    """,
                        eid=entity.entityId,
                        rid=role_id,
                    )
            
            # Project triplets as relationships
            for triplet in dossier.triplets:
                await session.run("""
                    MATCH (actor:Entity {entityId: $actor})
                    MATCH (target:Entity {entityId: $target})
                    MERGE (actor)-[t:TRIPLET {tripletId: $tid}]->(target)
                    SET t.name = $name,
                        t.mode = $mode,
                        t.stance = $stance,
                        t.roleId = $role
                """,
                    actor=triplet.actingEntityId,
                    target=triplet.targetEntityId,
                    tid=triplet.tripletId,
                    name=triplet.name,
                    mode=triplet.modeOfInteraction.value,
                    stance=triplet.stance.value,
                    role=triplet.actingRoleId,
                )
                stats["triplets"] += 1
            
            # Project relationships from RelationshipMatrix
            for rel in dossier.relationships:
                await session.run("""
                    MATCH (s {entityId: $source})
                    MATCH (t {entityId: $target})
                    MERGE (s)-[r:RELATES {relationshipId: $rid}]->(t)
                    SET r.type = $type,
                        r.description = $desc
                """,
                    source=rel.sourceId,
                    target=rel.targetId,
                    rid=rel.relationshipId,
                    type=rel.relationshipType,
                    desc=rel.description or "",
                )
                stats["relationships"] += 1
        
        logger.info(f"Mímir projected dossier to Neo4j: {stats}")
        return stats
    
    async def _create_constraints(self, session) -> None:
        """Create unique constraints"""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.entityId IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Role) REQUIRE r.roleId IS UNIQUE",
        ]
        for constraint in constraints:
            try:
                await session.run(constraint)
            except Exception as e:
                logger.debug(f"Constraint may already exist: {e}")
    
    async def query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query"""
        driver = await self._get_driver()
        if not driver:
            return []
        
        async with driver.session() as session:
            result = await session.run(cypher, params or {})
            records = await result.data()
            return records
    
    async def get_entity_context(self, entity_id: str) -> dict[str, Any]:
        """
        Get full context for an entity.
        
        Returns entity properties, roles, and relationships.
        """
        results = await self.query("""
            MATCH (e:Entity {entityId: $id})
            OPTIONAL MATCH (e)-[:HAS_ROLE]->(r:Role)
            OPTIONAL MATCH (e)-[t:TRIPLET]->(target:Entity)
            OPTIONAL MATCH (source:Entity)-[t2:TRIPLET]->(e)
            RETURN e as entity,
                   collect(DISTINCT r) as roles,
                   collect(DISTINCT {mode: t.mode, target: target.name}) as outbound,
                   collect(DISTINCT {mode: t2.mode, source: source.name}) as inbound
        """, {"id": entity_id})
        
        if not results:
            return {}
        
        r = results[0]
        return {
            "entity": dict(r["entity"]) if r["entity"] else {},
            "roles": [dict(role) for role in r["roles"] if role],
            "outbound_actions": r["outbound"],
            "inbound_actions": r["inbound"],
        }
    
    async def find_path(
        self,
        from_entity: str,
        to_entity: str,
        max_hops: int = 5,
    ) -> list[dict[str, Any]]:
        """Find path between two entities"""
        return await self.query(f"""
            MATCH path = shortestPath(
                (s:Entity {{entityId: $from}})-[*..{max_hops}]-(e:Entity {{entityId: $to}})
            )
            RETURN [n in nodes(path) | n.name] as path_names,
                   [r in relationships(path) | type(r)] as path_types
        """, {"from": from_entity, "to": to_entity})
    
    async def get_role_capabilities(self, role_id: str) -> list[dict[str, Any]]:
        """Get all capabilities for a role"""
        return await self.query("""
            MATCH (e:Entity)-[:HAS_ROLE]->(r:Role {roleId: $role})
            MATCH (e)-[t:TRIPLET]->(target:Entity)
            WHERE t.roleId = $role
            RETURN e.name as actor,
                   t.mode as mode,
                   target.name as target,
                   t.name as action_name
            ORDER BY e.name, t.mode
        """, {"role": role_id})
    
    async def clear(self) -> None:
        """Clear all projected data"""
        driver = await self._get_driver()
        if not driver:
            return
        
        async with driver.session() as session:
            await session.run("MATCH (n) DETACH DELETE n")
        
        logger.info("Mímir cleared graph projection")
    
    async def close(self) -> None:
        """Close Neo4j connection"""
        if self._driver:
            await self._driver.close()
            self._driver = None


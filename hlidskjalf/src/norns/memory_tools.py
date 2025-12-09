"""
Memory Tools - MCP tools for Raven cognitive architecture

Tools for interacting with:
- Huginn (state)
- Frigg (context)
- Muninn (memory)
- Hel (governance)
- Mímir (domain knowledge)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Global instances (initialized by CognitiveNorns)
_huginn = None
_frigg = None
_muninn = None
_hel = None
_mimir = None
_ollama = None


def init_memory_tools(huginn=None, frigg=None, muninn=None, hel=None, mimir=None, ollama=None):
    """Initialize memory tool instances"""
    global _huginn, _frigg, _muninn, _hel, _mimir, _ollama
    _huginn = huginn
    _frigg = frigg
    _muninn = muninn
    _hel = hel
    _mimir = mimir
    _ollama = ollama


# =============================================================================
# Huginn Tools (State)
# =============================================================================

@tool
def huginn_perceive(session_id: str) -> dict[str, Any]:
    """
    Perceive the current state for a session (Huginn).
    
    Returns the current turn state including utterance, intent, slots, and flags.
    This is a zero-latency operation reading from local cache.
    
    Args:
        session_id: The session ID to perceive
        
    Returns:
        Current session state
    """
    if not _huginn:
        return {"error": "Huginn not initialized"}
    
    state = _huginn.perceive(session_id)
    return state.model_dump()


@tool
async def huginn_set_flag(session_id: str, flag: str, value: bool = True) -> dict[str, Any]:
    """
    Set a routing/state flag for a session (Huginn).
    
    Flags are used for routing decisions and state tracking.
    
    Args:
        session_id: The session ID
        flag: The flag name to set
        value: The boolean value (default True)
        
    Returns:
        Updated state
    """
    if not _huginn:
        return {"error": "Huginn not initialized"}
    
    await _huginn.set_flag(session_id, flag, value)
    state = _huginn.perceive(session_id)
    return {"success": True, "flags": state.flags}


# =============================================================================
# Frigg Tools (Context)
# =============================================================================

@tool
def frigg_divine(session_id: str) -> dict[str, Any]:
    """
    Divine the persona/context for a session (Frigg).
    
    Returns the PersonaSnapshot including user tags, preferences, risk flags,
    and applicable triplets.
    
    Args:
        session_id: The session ID to divine
        
    Returns:
        Persona snapshot for the user
    """
    if not _frigg:
        return {"error": "Frigg not initialized"}
    
    persona = _frigg.divine(session_id)
    if not persona:
        return {"error": "No persona found for session"}
    
    return persona.to_context_dict()


@tool
async def frigg_update_tags(session_id: str, tags: list[str]) -> dict[str, Any]:
    """
    Add tags to a user's persona (Frigg).
    
    Tags are used for classification and routing (e.g., "repeat_caller", "vip").
    
    Args:
        session_id: The session ID
        tags: List of tags to add
        
    Returns:
        Updated persona
    """
    if not _frigg:
        return {"error": "Frigg not initialized"}
    
    persona = await _frigg.update_tags(session_id, *tags)
    if not persona:
        return {"error": "Persona not found"}
    
    return {"success": True, "tags": persona.tags}


# =============================================================================
# Muninn Tools (Memory)
# =============================================================================

@tool
async def muninn_recall(
    query: str, 
    k: int = 5,
    memory_type: str | None = None,
    domain: str | None = None,
) -> list[dict[str, Any]]:
    """
    Recall memories from Muninn using semantic search.
    
    Searches long-term memory for relevant fragments based on the query.
    Results are ordered by relevance and weight.
    
    Args:
        query: The search query
        k: Number of results to return (default 5)
        memory_type: Optional filter by type (episodic, semantic, procedural)
        domain: Optional filter by domain
        
    Returns:
        List of relevant memory fragments
    """
    if not _muninn:
        return [{"error": "Muninn not initialized"}]
    
    from src.memory.muninn.store import MemoryType
    
    mem_type = None
    if memory_type:
        try:
            mem_type = MemoryType(memory_type)
        except ValueError:
            pass
    
    memories = await _muninn.recall(
        query=query,
        k=k,
        memory_type=mem_type,
        domain=domain,
    )
    
    return [
        {
            "id": m.id,
            "type": m.type.value,
            "content": m.content[:500],  # Truncate for response
            "domain": m.domain,
            "weight": m.weight,
            "references": m.references,
        }
        for m in memories
    ]


@tool
async def muninn_remember(
    content: str,
    domain: str = "general",
    topic: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Store a new memory in Muninn.
    
    Creates an episodic memory fragment that can be recalled later.
    Memory will be subject to Hel's reinforcement and decay.
    
    Args:
        content: The content to remember
        domain: Domain category (default "general")
        topic: Optional topic tag
        user_id: Optional user association
        session_id: Optional session association
        
    Returns:
        Created memory info
    """
    if not _muninn:
        return {"error": "Muninn not initialized"}
    
    from src.memory.muninn.store import MemoryFragment, MemoryType
    
    fragment = MemoryFragment(
        type=MemoryType.EPISODIC,
        content=content,
        domain=domain,
        topic=topic,
        user_id=user_id,
        session_id=session_id,
    )
    
    memory_id = await _muninn.remember(fragment)
    return {"success": True, "memory_id": memory_id}


# =============================================================================
# Hel Tools (Governance)
# =============================================================================

@tool
async def hel_reinforce(memory_id: str, importance: float = 1.0) -> dict[str, Any]:
    """
    Reinforce a memory (Hel).
    
    Increases the weight of a memory, making it more likely to be recalled
    and less likely to be pruned.
    
    Args:
        memory_id: The memory ID to reinforce
        importance: Importance factor (0.0-2.0, default 1.0)
        
    Returns:
        Updated weight
    """
    if not _hel or not _muninn:
        return {"error": "Hel or Muninn not initialized"}
    
    memory = await _muninn.get(memory_id)
    if not memory:
        return {"error": f"Memory {memory_id} not found"}
    
    new_weight = _hel.reinforce(memory, importance)
    await _muninn.remember(memory)  # Persist updated weight
    
    return {
        "success": True,
        "memory_id": memory_id,
        "new_weight": new_weight,
        "references": memory.references,
    }


@tool
def hel_stats() -> dict[str, Any]:
    """
    Get memory governance statistics (Hel).
    
    Returns statistics about memory weights, promotion candidates,
    and prune candidates.
    
    Returns:
        Memory statistics
    """
    if not _hel or not _muninn:
        return {"error": "Hel or Muninn not initialized"}
    
    # Get stats from local index
    memories = list(_muninn._memory_index.values())
    return _hel.get_stats(memories)


# =============================================================================
# Mímir Tools (Domain Knowledge)
# =============================================================================

@tool
def mimir_consult(role_id: str, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """
    Consult Mímir for valid actions (triplets) for a role.
    
    Returns the AgenticTriplets that the role can perform given the context.
    Evaluates AccessGates with JMESPath conditions.
    
    Args:
        role_id: The role to query for
        context: Optional context for gate evaluation
        
    Returns:
        List of valid triplets
    """
    if not _mimir:
        return [{"error": "Mímir not initialized"}]
    
    triplets = _mimir.consult(role_id, context or {})
    
    return [
        {
            "triplet_id": t.tripletId,
            "name": t.name,
            "mode": t.modeOfInteraction.value,
            "target": t.targetEntityId,
            "stance": t.stance.value,
        }
        for t in triplets
    ]


@tool
def mimir_can_act(
    role_id: str,
    entity_id: str,
    mode: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Check if a role can perform a specific action (Mímir).
    
    Verifies if the role has permission to perform the mode on the entity.
    
    Args:
        role_id: The role to check
        entity_id: The target entity
        mode: The mode of interaction (CREATE, READ, UPDATE, DELETE, etc.)
        context: Optional context for gate evaluation
        
    Returns:
        Permission check result
    """
    if not _mimir:
        return {"error": "Mímir not initialized"}
    
    from src.memory.mimir.models import ModeOfInteraction
    
    try:
        mode_enum = ModeOfInteraction(mode.upper())
    except ValueError:
        return {"error": f"Invalid mode: {mode}"}
    
    allowed = _mimir.can_act(role_id, entity_id, mode_enum, context or {})
    
    if not allowed:
        explanation = _mimir.explain_denial(role_id, entity_id, mode_enum, context or {})
        return {"allowed": False, "reason": explanation}
    
    return {"allowed": True}


@tool
def mimir_entity(entity_id: str) -> dict[str, Any]:
    """
    Get entity definition from Mímir.
    
    Returns the full entity definition from the DIS dossier.
    
    Args:
        entity_id: The entity ID to look up
        
    Returns:
        Entity definition
    """
    if not _mimir:
        return {"error": "Mímir not initialized"}
    
    entity = _mimir.dossier.get_entity(entity_id)
    if not entity:
        return {"error": f"Entity {entity_id} not found"}
    
    return entity.model_dump()


# =============================================================================
# Procedural Memory Tools (Skills Management)
# =============================================================================

@tool
async def skills_list(
    role: str | None = None,
    domain: str | None = None,
    min_weight: float = 0.1,
) -> list[dict[str, Any]]:
    """
    List all skills (procedural memories).
    
    Args:
        role: Filter by role (e.g., "sre", "devops")
        domain: Filter by domain
        min_weight: Minimum weight threshold (default 0.1)
        
    Returns:
        List of skills with metadata
    """
    if not _muninn:
        return [{"error": "Muninn not initialized"}]
    
    from src.memory.muninn.procedural import ProceduralMemory
    
    proc_mem = ProceduralMemory(_muninn)
    skills = await proc_mem.list_skills(role=role, domain=domain, min_weight=min_weight)
    
    return [
        {
            "id": s.id,
            "name": s.features.get("name", ""),
            "summary": s.summary,
            "roles": s.features.get("roles", []),
            "weight": s.weight,
            "references": s.references,
            "version": s.features.get("version", "1.0.0"),
        }
        for s in skills
    ]


@tool
async def skills_retrieve(
    query: str,
    role: str | None = None,
    domain: str | None = None,
    k: int = 5,
) -> list[dict[str, Any]]:
    """
    Retrieve relevant skills using RAG (semantic search).
    
    Supports @skill_name tags for direct lookup, e.g.:
    - "How do I @file-editing safely?" -> returns file-editing skill directly
    - "@terminal-commands @docker-operations" -> returns both skills
    
    Args:
        query: Task description or search query (can include @skill_name tags)
        role: Optional role filter (only for semantic search, not direct lookups)
        domain: Optional domain filter
        k: Number of skills to retrieve
        
    Returns:
        List of relevant skills with content
    """
    import re
    
    if not _muninn:
        logger.warning("skills_retrieve: Muninn not initialized")
        return [{"error": "Muninn not initialized"}]
    
    from src.memory.muninn.procedural import ProceduralMemory
    
    proc_mem = ProceduralMemory(_muninn)
    
    # Parse @skill_name tags for direct lookup
    skill_tags = re.findall(r'@([\w-]+)', query)
    direct_skills = []
    
    if skill_tags:
        # Direct lookup for tagged skills
        direct_skills = proc_mem.get_skills_by_names(skill_tags)
        logger.info(f"skills_retrieve: direct lookup for {skill_tags} found {len(direct_skills)} skills")
        
        # If we found all requested skills via direct lookup, return them
        if len(direct_skills) >= k or len(direct_skills) == len(skill_tags):
            return [
                {
                    "id": s.id,
                    "name": s.features.get("name", ""),
                    "summary": s.summary,
                    "content": s.content,
                    "roles": s.features.get("roles", []),
                    "weight": s.weight,
                    "dependencies": s.features.get("dependencies", []),
                }
                for s in direct_skills[:k]
            ]
    
    # Fall back to semantic search for remaining slots
    remaining_k = k - len(direct_skills)
    if remaining_k > 0:
        # Remove @tags from query for semantic search
        clean_query = re.sub(r'@[\w-]+\s*', '', query).strip()
        if clean_query:
            semantic_skills = await proc_mem.retrieve_skills(
                query=clean_query, 
                role=role, 
                domain=domain, 
                k=remaining_k
            )
            # Combine direct lookups with semantic results (avoid duplicates)
            direct_ids = {s.id for s in direct_skills}
            for s in semantic_skills:
                if s.id not in direct_ids:
                    direct_skills.append(s)
    
    logger.info(f"skills_retrieve: returning {len(direct_skills)} total skills")
    
    return [
        {
            "id": s.id,
            "name": s.features.get("name", ""),
            "summary": s.summary,
            "content": s.content,
            "roles": s.features.get("roles", []),
            "weight": s.weight,
            "dependencies": s.features.get("dependencies", []),
        }
        for s in direct_skills[:k]
    ]


@tool
async def skills_add(
    name: str,
    content: str,
    roles: list[str],
    summary: str,
    domain: str = "ravenhelm",
    tags: list[str] | None = None,
    dependencies: list[str] | None = None,
) -> dict[str, Any]:
    """
    Add a new skill to procedural memory.
    
    Args:
        name: Skill identifier (kebab-case)
        content: Full skill instructions (markdown)
        roles: Applicable roles (e.g., ["sre", "devops"])
        summary: Brief description
        domain: Knowledge domain
        tags: Optional tags
        dependencies: Optional prerequisite skills
        
    Returns:
        Created skill info
    """
    if not _muninn:
        return {"error": "Muninn not initialized"}
    
    from src.memory.muninn.procedural import ProceduralMemory
    
    proc_mem = ProceduralMemory(_muninn)
    memory_id = await proc_mem.add_skill(
        name=name,
        content=content,
        roles=roles,
        summary=summary,
        domain=domain,
        tags=tags or [],
        dependencies=dependencies or [],
    )
    
    return {"success": True, "skill_id": memory_id, "name": name}


@tool
async def skills_update(
    skill_id: str,
    content: str | None = None,
    summary: str | None = None,
    roles: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Update an existing skill.
    
    Args:
        skill_id: Skill memory ID
        content: New content (optional)
        summary: New summary (optional)
        roles: New roles (optional)
        tags: New tags (optional)
        
    Returns:
        Update status
    """
    if not _muninn:
        return {"error": "Muninn not initialized"}
    
    from src.memory.muninn.procedural import ProceduralMemory
    
    proc_mem = ProceduralMemory(_muninn)
    success = await proc_mem.update_skill(
        skill_id=skill_id,
        content=content,
        summary=summary,
        roles=roles,
        tags=tags,
    )
    
    return {"success": success, "skill_id": skill_id}


@tool
async def skills_delete(skill_id: str) -> dict[str, Any]:
    """
    Delete a skill (sets weight to 0).
    
    Args:
        skill_id: Skill memory ID
        
    Returns:
        Deletion status
    """
    if not _muninn:
        return {"error": "Muninn not initialized"}
    
    from src.memory.muninn.procedural import ProceduralMemory
    
    proc_mem = ProceduralMemory(_muninn)
    success = await proc_mem.delete_skill(skill_id)
    
    return {"success": success, "skill_id": skill_id}


# =============================================================================
# Document Ingestion Tools
# =============================================================================

@tool
async def documents_crawl_page(
    url: str,
    domain: str = "external",
) -> dict[str, Any]:
    """
    Crawl a single web page and store in semantic memory.
    
    Uses Firecrawl to extract LLM-friendly content.
    
    Args:
        url: Page URL to crawl
        domain: Domain classification
        
    Returns:
        Crawl results with memory IDs
    """
    from src.services.document_ingestion import DocumentIngestionService
    
    service = DocumentIngestionService()
    memory_ids = await service.crawl_page(url=url, domain=domain)
    
    return {
        "success": True,
        "url": url,
        "chunks": len(memory_ids),
        "memory_ids": memory_ids,
    }


@tool
async def documents_crawl_site(
    url: str,
    domain: str = "external",
    max_depth: int = 2,
    max_pages: int = 50,
) -> dict[str, Any]:
    """
    Crawl an entire website and store pages in semantic memory.
    
    Args:
        url: Root URL to crawl
        domain: Domain classification
        max_depth: Maximum link depth
        max_pages: Maximum pages to crawl
        
    Returns:
        Crawl statistics
    """
    from src.services.document_ingestion import DocumentIngestionService
    
    service = DocumentIngestionService()
    result = await service.crawl_site(
        url=url,
        domain=domain,
        max_depth=max_depth,
        max_pages=max_pages,
    )
    
    return result


@tool
async def documents_search(
    query: str,
    domain: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Search ingested documents.
    
    Args:
        query: Search query
        domain: Optional domain filter
        limit: Maximum results
        
    Returns:
        Matching documents
    """
    from src.services.document_ingestion import DocumentIngestionService
    
    service = DocumentIngestionService()
    results = await service.search_documents(query=query, domain=domain, limit=limit)
    
    return results


@tool
async def documents_stats(domain: str | None = None) -> dict[str, Any]:
    """
    Get statistics about ingested documents.
    
    Args:
        domain: Optional domain filter
        
    Returns:
        Document statistics
    """
    from src.services.document_ingestion import DocumentIngestionService
    
    service = DocumentIngestionService()
    stats = await service.get_crawl_stats(domain=domain)
    
    return stats


# =============================================================================
# Graph Query Tools (Neo4j) - with graceful fallbacks
# =============================================================================

# Cache for structural memory to avoid recreating connection each call
_structural_memory = None


async def _get_structural_memory():
    """Get or create structural memory instance with env-based config."""
    global _structural_memory
    
    import os
    
    if _structural_memory is None:
        from src.memory.muninn.structural import StructuralMemory
        
        neo4j_uri = os.environ.get("NEO4J_URI", "bolt://neo4j:7688")
        neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
        neo4j_password = os.environ.get("NEO4J_PASSWORD", "ravenhelm")
        memgraph_uri = os.environ.get("MEMGRAPH_URI")
        
        _structural_memory = StructuralMemory(
            neo4j_uri=neo4j_uri,
            neo4j_auth=(neo4j_user, neo4j_password),
            memgraph_uri=memgraph_uri,
        )
    
    return _structural_memory


async def _check_neo4j_available() -> bool:
    """Check if Neo4j is available for queries."""
    try:
        structural = await _get_structural_memory()
        driver = await structural._get_neo4j()
        if driver is None:
            return False
        # Try a simple query
        async with driver.session() as session:
            await session.run("RETURN 1")
        return True
    except Exception as e:
        logger.warning(f"Neo4j not available: {e}")
        return False


def _fallback_skill_dependencies(skill_id: str) -> list[dict[str, Any]]:
    """Fallback: get dependencies from Muninn procedural memory."""
    if not _muninn:
        return []
    
    # Look up skill in local memory and extract dependencies from features
    for mem in _muninn._memory_index.values():
        if mem.id == skill_id or mem.features.get("name") == skill_id:
            deps = mem.features.get("dependencies", [])
            return [{"name": dep, "source": "muninn_features"} for dep in deps]
    return []


def _fallback_skills_for_role(role_id: str) -> list[dict[str, Any]]:
    """Fallback: get skills from Muninn procedural memory filtered by role."""
    if not _muninn:
        return []
    
    from src.memory.muninn.store import MemoryType
    
    skills = []
    for mem in _muninn._memory_index.values():
        if mem.type == MemoryType.PROCEDURAL and mem.topic == "skill":
            roles = mem.features.get("roles", [])
            if role_id in roles or not role_id:
                skills.append({
                    "id": mem.id,
                    "name": mem.features.get("name", ""),
                    "weight": mem.weight,
                    "source": "muninn_fallback",
                })
    
    return sorted(skills, key=lambda x: x.get("weight", 0), reverse=True)


@tool
async def graph_skill_dependencies(skill_id: str, recursive: bool = True) -> list[dict[str, Any]]:
    """
    Get dependencies for a skill from Neo4j graph.
    
    Falls back to Muninn procedural memory if Neo4j is unavailable.
    
    Args:
        skill_id: Skill memory ID or name
        recursive: Include transitive dependencies
        
    Returns:
        List of required skills
    """
    # Try Neo4j first
    if await _check_neo4j_available():
        try:
            structural = await _get_structural_memory()
            deps = await structural.get_skill_dependencies(skill_id, recursive=recursive)
            
            if deps:
                return [
                    {
                        "id": dep.node_id,
                        "name": dep.name,
                        "summary": dep.properties.get("summary", ""),
                        "source": "neo4j",
                    }
                    for dep in deps
                ]
        except Exception as e:
            logger.warning(f"Neo4j query failed, using fallback: {e}")
    
    # Fallback to Muninn
    fallback_deps = _fallback_skill_dependencies(skill_id)
    if fallback_deps:
        return fallback_deps
    
    return [{
        "note": "Neo4j not available and no dependencies found in Muninn",
        "skill_id": skill_id,
        "hint": "Ensure Neo4j is running or dependencies are defined in skill YAML frontmatter",
    }]


@tool
async def graph_skills_for_role(role_id: str, include_inherited: bool = True) -> list[dict[str, Any]]:
    """
    Get all skills available to a role from Neo4j graph.
    
    Falls back to Muninn procedural memory if Neo4j is unavailable.
    
    Args:
        role_id: Role identifier (e.g., "sre", "devops")
        include_inherited: Include parent role skills
        
    Returns:
        List of authorized skills
    """
    # Try Neo4j first
    if await _check_neo4j_available():
        try:
            structural = await _get_structural_memory()
            skills = await structural.get_skills_for_role(role_id, include_inherited=include_inherited)
            
            if skills:
                return [
                    {
                        "id": skill.node_id,
                        "name": skill.name,
                        "weight": skill.properties.get("weight", 0.5),
                        "source": "neo4j",
                    }
                    for skill in skills
                ]
        except Exception as e:
            logger.warning(f"Neo4j query failed, using fallback: {e}")
    
    # Fallback to Muninn
    fallback_skills = _fallback_skills_for_role(role_id)
    if fallback_skills:
        return fallback_skills
    
    return [{
        "note": f"Neo4j not available and no skills found in Muninn for role '{role_id}'",
        "hint": "Ensure Neo4j is running or skills have roles defined in YAML frontmatter",
    }]


@tool
async def graph_skill_workflow(start_skill_id: str) -> list[dict[str, Any]]:
    """
    Get typical workflow sequence starting from a skill.
    
    Follows FOLLOWS relationships to build workflow chain.
    Falls back to showing just the starting skill if Neo4j is unavailable.
    
    Args:
        start_skill_id: Starting skill ID or name
        
    Returns:
        Ordered workflow steps
    """
    # Try Neo4j first
    if await _check_neo4j_available():
        try:
            structural = await _get_structural_memory()
            workflow = await structural.get_skill_workflow(start_skill_id)
            
            if workflow:
                return [
                    {
                        "id": step.node_id,
                        "name": step.name,
                        "summary": step.properties.get("summary", ""),
                        "source": "neo4j",
                    }
                    for step in workflow
                ]
        except Exception as e:
            logger.warning(f"Neo4j query failed, using fallback: {e}")
    
    # Fallback: just return the skill itself from Muninn
    if _muninn:
        for mem in _muninn._memory_index.values():
            if mem.id == start_skill_id or mem.features.get("name") == start_skill_id:
                return [{
                    "id": mem.id,
                    "name": mem.features.get("name", start_skill_id),
                    "summary": mem.summary or "",
                    "source": "muninn_fallback",
                    "note": "Workflow relationships require Neo4j - showing single skill only",
                }]
    
    return [{
        "note": "Neo4j not available and skill not found in Muninn",
        "skill_id": start_skill_id,
        "hint": "Ensure Neo4j is running for workflow queries",
    }]


# =============================================================================
# Ollama Tools (Local LLM)
# =============================================================================

def _sanitize_text(text: str) -> str:
    """Sanitize text for safe JSON serialization."""
    if not text:
        return ""
    # Replace problematic characters
    return text.replace('\x00', '').strip()


@tool
async def ollama_analyze(
    content: str,
    task: str = "summarize",
    context: str | None = None,
) -> dict[str, Any]:
    """
    Use local Ollama model for analysis tasks.
    
    This runs locally without API costs - great for:
    - Summarization
    - Pattern extraction
    - Entity extraction
    - Classification
    
    Args:
        content: The content to analyze
        task: The analysis task (summarize, extract_entities, classify, reason)
        context: Optional context to guide analysis
        
    Returns:
        Analysis result
    """
    if not _ollama:
        return {"error": "Ollama not initialized", "hint": "Local LLM not available"}
    
    prompts = {
        "summarize": f"Summarize the following content concisely:\n\n{content}",
        "extract_entities": f"Extract key entities (people, places, concepts) from:\n\n{content}\n\nReturn as a bulleted list.",
        "classify": f"Classify the intent and topic of:\n\n{content}\n\nReturn: intent, topic, confidence",
        "reason": f"Analyze and reason about:\n\n{content}\n\nContext: {context or 'None'}\n\nProvide your analysis:",
    }
    
    prompt = prompts.get(task, f"{task}:\n\n{content}")
    
    try:
        result = await _ollama.generate(prompt)
        return {"task": task, "result": _sanitize_text(result), "model": "local"}
    except Exception as e:
        return {"error": str(e)}


@tool
async def ollama_embed(text: str) -> dict[str, Any]:
    """
    Get embeddings using local Ollama model.
    
    Useful for:
    - Similarity comparisons
    - Semantic search preparation
    - Clustering content
    
    Args:
        text: Text to embed
        
    Returns:
        Embedding vector info
    """
    if not _ollama:
        return {"error": "Ollama not initialized"}
    
    try:
        embedding = await _ollama.embed(text)
        return {
            "dimension": len(embedding),
            "preview": embedding[:5] if embedding else [],
            "model": "nomic-embed-text",
        }
    except Exception as e:
        return {"error": str(e)}


@tool
async def ollama_chat(
    message: str,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """
    Chat with local Ollama model for cognitive tasks.
    
    Useful for:
    - Breaking down complex problems
    - Generating alternatives
    - Validating reasoning
    
    Args:
        message: The message to send
        system_prompt: Optional system prompt for context
        
    Returns:
        Chat response
    """
    if not _ollama:
        return {"error": "Ollama not initialized"}
    
    try:
        response = await _ollama.chat(
            [{"role": "user", "content": message}],
            system=system_prompt,
        )
        return {"response": _sanitize_text(response), "model": "llama3.1:8b"}
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Export all tools
# =============================================================================

MEMORY_TOOLS = [
    # Huginn (State)
    huginn_perceive,
    huginn_set_flag,
    # Frigg (Context)
    frigg_divine,
    frigg_update_tags,
    # Muninn (Memory)
    muninn_recall,
    muninn_remember,
    # Hel (Governance)
    hel_reinforce,
    hel_stats,
    # Mímir (Domain Knowledge)
    mimir_consult,
    mimir_can_act,
    mimir_entity,
    # Procedural Memory (Skills)
    skills_list,
    skills_retrieve,
    skills_add,
    skills_update,
    skills_delete,
    # Document Ingestion
    documents_crawl_page,
    documents_crawl_site,
    documents_search,
    documents_stats,
    # Graph Queries (Neo4j)
    graph_skill_dependencies,
    graph_skills_for_role,
    graph_skill_workflow,
    # Ollama (Local LLM)
    ollama_analyze,
    ollama_embed,
    ollama_chat,
]


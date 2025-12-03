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
    # Huginn
    huginn_perceive,
    huginn_set_flag,
    # Frigg
    frigg_divine,
    frigg_update_tags,
    # Muninn
    muninn_recall,
    muninn_remember,
    # Hel
    hel_reinforce,
    hel_stats,
    # Mímir
    mimir_consult,
    mimir_can_act,
    mimir_entity,
    # Ollama (Local LLM)
    ollama_analyze,
    ollama_embed,
    ollama_chat,
]


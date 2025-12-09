"""
The Norns Agent — LangGraph Deep Agent implementation.

The sisters maintain TODO lists, can manipulate the workspace, spawn specialists,
and persist short-term context in Redis.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Annotated, Literal, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph, add_messages
from langgraph.prebuilt import ToolNode

from src.core.config import get_settings

logger = logging.getLogger(__name__)
from src.norns.planner import generate_todo_plan
from src.norns.tools import NORN_TOOLS
from src.norns.skills import get_skills_context
from src.services.memory import RedisShortTermMemory, get_short_term_memory


class TodoItem(TypedDict, total=False):
    id: str
    description: str
    status: str
    owner: Optional[str]


class NornState(TypedDict, total=False):
    """Norn agent state - compatible with LangGraph API."""
    # Required: messages with add_messages reducer for API compatibility
    messages: Annotated[list[BaseMessage], add_messages]
    # Optional fields with defaults handled in nodes
    current_norn: str
    context: dict
    todos: list[TodoItem]
    # Session tracking for cognitive architecture
    session_id: str
    # Cognitive context injected into system prompt
    cognitive_context: str
    llm_config: dict


PLANNING_KEYWORDS = [
    "plan",
    "todo",
    "tasks",
    "deploy",
    "implement",
    "build",
    "upgrade",
    "migrate",
]


def _llm_config_to_dict(config) -> dict:
    return {
        "reasoning": {
            "provider": config.reasoning.provider,
            "model": config.reasoning.model,
            "temperature": config.reasoning.temperature,
        },
        "tools": {
            "provider": config.tools.provider,
            "model": config.tools.model,
            "temperature": config.tools.temperature,
        },
        "subagents": {
            "provider": config.subagents.provider,
            "model": config.subagents.model,
            "temperature": config.subagents.temperature,
        },
    }


def _fetch_llm_config(session_id: str):
    from src.norns.memory_tools import _huginn

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_huginn.get_llm_config(session_id))
    finally:
        loop.close()


def _get_session_llm_config(session_id: str) -> dict | None:
    """
    Get LLM configuration for a session via event cache or Huginn state.
    """
    import logging

    logger = logging.getLogger(__name__)

    # 1. Try registry cache fed by events
    try:
        settings = get_settings()
        registry = get_llm_config_registry(settings.KAFKA_BOOTSTRAP)
        registry.start()
        cached = registry.get_config(session_id)
        if cached:
            return cached
    except Exception as exc:
        logger.debug("LLM config registry unavailable: %s", exc)

    # 2. Fall back to Huginn perception/Redis
    try:
        from src.norns.memory_tools import _huginn

        if not _huginn:
            return None

        state = _huginn.perceive(session_id)
        if (not state or not getattr(state, "llm_config", None)) and hasattr(
            _huginn, "get_llm_config"
        ):
            # Use Redis fallback to ensure we see updates from other processes.
            config = _fetch_llm_config(session_id)
            if config:
                return _llm_config_to_dict(config)

        if state and getattr(state, "llm_config", None):
            return _llm_config_to_dict(state.llm_config)
    except Exception as exc:
        logger.debug(f"Could not get LLM config from Huginn: {exc}")

    return None

def build_norns_system_prompt() -> str:
    """Build the Norns supervisor prompt following the canonical format."""
    return """You are Norns, the DeepAgent / LangGraph supervisor for the Quant AI Ravenhelm platform.

##################################################
### HOW YOU MUST THINK (MANDATORY FORMAT)
##################################################
For every task:
[THINK]
- Do full chain-of-thought: clarify intent, inspect state/context, plan subtasks, choose tools/subagents, consider risks.
- Be detailed and explicit here. This block is NOT visible to the user.
[/THINK]

Then produce a clean Markdown answer with NO internal reasoning.

##################################################
### PROMPT-WRITING PRINCIPLES
##################################################
Always:
- Put instructions BEFORE context, and fence input:

Instruction:
<what to do>

Text:
\"\"\"<text or payload>\"\"\"

- Be explicit about:
  - outcome (what "done" is)
  - length ("3–5 sentences", "8–12 bullets", "~1 page")
  - format ("Markdown sections", "JSON object", "Python code block")
  - style ("runbook", "executive summary", "architecture spec")
  - constraints ("must use platform_net", "read-only", "no PII")

- Show desired output shape when you need structured results:

Example:
Company names: <comma_separated_list>
People names: <comma_separated_list>
Topics: <comma_separated_list>
Themes: <comma_separated_list>

- Escalate clarity: zero-shot → add 1–2 examples → only then use a specialized/fine-tuned agent.
- Replace "do NOT X" with "instead do Y".
- For code, use leading tokens:
  - Python: start with "import"
  - SQL: start with "SELECT"
- When spawning subagents, ALWAYS specify:
  - role
  - goal
  - inputs/context
  - constraints
  - required output format (with an example).

##################################################
### FABRICS & ROLES
##################################################
Huginn = State (L3/L4)
- "What is happening now?"
- Turn/session truth: utterance, intent, workflow step, slots, pending actions.
- Provided via state tools / cache. Treat given state as ground truth; do NOT reach back to raw logs/STT yourself.

Frigg = Context (Persona & Policy)
- "Who is this & what matters now?"
- Persona Snapshot: preferences, risk flags, recent episodes, relationship/role.
- Use context tools; do NOT query raw user DBs in the hot path.

Muninn = Long-Term Memory (Itsuki + Postgres/pgvector)
- Episodic, semantic, procedural memory + RAG.
- Access only via memory tools (e.g., memory.query / memory.promote / memory.reinforce / memory.debug).
- Do NOT query underlying databases or vector stores directly.

Hel = Governance & Quarantine
- Safety, DLQ, destructive forgetting and nullification.
- Use hel.quarantine / hel.redact / hel.restore_from_quarantine / hel.stats when memory appears unsafe, stale, or corrupted.

Hard rule:
No agent (including you) keeps its own long-lived state. All persistence uses Huginn, Frigg, Muninn, or Hel.

##################################################
### RAVENHELM PLATFORM CONSTRAINTS
##################################################
Ingress:
- Traefik (ravenhelm-proxy) is the ONLY HTTP ingress. Never design alternate public gateways.

Networking:
- platform_net is the canonical shared Docker bridge.
- New services must declare platform_net as external: true.
- Do NOT introduce ad-hoc bridges (e.g., gitlab-network).

Identity & Secrets:
- Identities via Zitadel only.
- ALL runtime secrets live in LocalStack Secrets Manager (e.g., ravenhelm/dev/postgres/credentials, ravenhelm/dev/gitlab/mcp_service).
- Never propose .env secrets or hard-coded tokens.
- Never commit PATs, webhook tokens, or NextAuth secrets.

SPIRE / SPIFFE:
- Internal traffic (Postgres, Redis, NATS, MCP, etc.) uses SPIRE-based mTLS.
- New workloads must use configs under config/spiffe-helper/.
- Traefik forwards to mTLS backends via serversTransport entries in ravenhelm-proxy/dynamic.yml.

Work Management & Docs:
- GitLab issues are the source of truth:
  - exactly one type:: label
  - exactly one workflow:: label
  - appropriate area:: and okr:: labels
- Norns automation only acts on issues with BOTH actor::norns AND workflow::ready.
- docs/wiki and docs/runbooks are authoritative:
  - runbooks follow RUNBOOK-0xx; update the catalog on changes.
  - ADRs live in docs/architecture.
  - Update PROJECT_PLAN.md and docs/LESSONS_LEARNED.md when proposing material arch/ops changes.

Operator Preferences:
- Always provide actionable steps + verification commands/checks.
- Use absolute repo paths where possible (e.g., /Users/nwalker/Development/hlidskjalf/...).
- For any change impacting shared services, governance, or compliance:
  - reference the Enterprise Multi-Platform Architecture Scaffold
  - state whether you align, extend, or intentionally deviate.

##################################################
### DECISION LOOP
##################################################
Internally (inside [THINK]) you will:
1) Clarify intent and "done" (artifact, decision, plan).
2) Inspect Huginn state + Frigg persona.
3) Decompose into ordered subtasks.
4) Decide tool vs subagent for each subtask.
5) Call memory tools (Muninn, e.g. memory.query) when domain knowledge/docs/history are needed; scope by domain/doc_type.
6) Route unsafe/stale/incorrect memories through Hel.
7) Integrate tool/subagent outputs, resolving conflicts using reliability, recency, and consistency with state/context.

Then:
- Respond in Markdown.
- State what you did.
- Surface assumptions, risks, and dependencies.
- List explicit next steps (for humans or agents).
- Include verification steps for any operational change.

##################################################
### STYLE
##################################################
Be structured and direct. Use headings and bullets. No filler. You are a supervisor, not a chatty assistant.
"""

# Static prompt for backwards compatibility
NORNS_SYSTEM_PROMPT = build_norns_system_prompt()


def format_todo_overview(todos: list[TodoItem]) -> str:
    if not todos:
        return "No TODOs recorded. Create them when Odin asks for sustained work."
    lines = []
    for item in todos:
        status = item.get("status", "pending")
        owner = item.get("owner", "Norns")
        desc = item.get("description", "")
        # Handle case where description might be a list (multi-modal content)
        if isinstance(desc, list):
            desc = " ".join(str(d) if not isinstance(d, dict) else d.get("text", str(d)) for d in desc)
        desc = str(desc).strip() if desc else ""
        lines.append(f"- [{status}] {item.get('id', '?')}: {desc} ({owner})")
    return "\n".join(lines)


def extract_text_content(content) -> str:
    """Extract text from message content (handles both string and list formats)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Handle multi-modal content blocks
        texts = []
        for block in content:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return " ".join(texts)
    return str(content) if content else ""


def determine_norn(content) -> str:
    text = extract_text_content(content).lower()
    if any(word in text for word in ["past", "history", "urðr", "urdr"]):
        return "urd"
    if any(word in text for word in ["future", "plan", "shall", "skuld"]):
        return "skuld"
    return "verdandi"


def should_plan(state: NornState) -> bool:
    if not state["messages"]:
        return False
    last = state["messages"][-1]
    if not isinstance(last, HumanMessage):
        return False
    text = extract_text_content(last.content).lower()
    if "reset plan" in text or "replan" in text or "new plan" in text:
        return True
    if state.get("todos"):
        return False
    return any(keyword in text for keyword in PLANNING_KEYWORDS)


def router(state: NornState) -> Literal["plan", "chat"]:
    return "plan" if should_plan(state) else "chat"


def planner_node(state: NornState) -> NornState:
    last_human = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
    if not last_human:
        return state
    plan = generate_todo_plan(last_human.content)
    return {**state, "todos": plan}


async def get_llm_for_interaction(interaction_type: str):
    """
    Get LLM instance from database configuration.
    
    Args:
        interaction_type: One of 'reasoning', 'tools', 'subagents', 'planning'
        
    Returns:
        Configured LLM instance with tools bound
    """
    import logging
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from src.models.llm_config import InteractionType
    from src.services.llm_config import LLMConfigService
    
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    try:
        # Create async session
        engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as session:
            config_service = LLMConfigService(session)
            
            # Map string to enum
            interaction_map = {
                "reasoning": InteractionType.REASONING,
                "tools": InteractionType.TOOLS,
                "subagents": InteractionType.SUBAGENTS,
                "planning": InteractionType.PLANNING,
            }
            
            interaction_enum = interaction_map.get(interaction_type, InteractionType.REASONING)
            
            # Get LLM with tools bound
            llm = await config_service.get_llm_with_tools(
                interaction_enum,
                NORN_TOOLS
            )
            
            logger.info(f"Loaded LLM for {interaction_type} from database config")
            return llm
            
    except Exception as e:
        logger.error(f"Failed to load LLM from config: {e}")
        logger.warning("Falling back to default OpenAI configuration")
        
        # Fallback to OpenAI with environment variable
        from langchain_openai import ChatOpenAI
        import os
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("No LLM configuration available and OPENAI_API_KEY not set")
        
        # Use appropriate model for interaction type
        model_map = {
            "reasoning": "gpt-4o",
            "tools": "gpt-4o-mini",
            "subagents": "gpt-4o-mini",
            "planning": "gpt-4o",
        }
        
        model = model_map.get(interaction_type, "gpt-4o")
        llm = ChatOpenAI(model=model, temperature=0.7)
        
        return llm.bind_tools(NORN_TOOLS)


def create_llm():
    """
    Create LLM for Norns reasoning (synchronous wrapper).
    
    This is a compatibility function that wraps the async config service.
    Uses a new event loop for thread-safety in ThreadPoolExecutor.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(get_llm_for_interaction("reasoning"))
    except Exception as e:
        logger.error(f"Failed to create LLM: {e}")
        raise
    finally:
        loop.close()


def _build_cognitive_context(state: NornState) -> str:
    """Build cognitive context from Huginn/Frigg/Muninn (sync wrapper)."""
    import logging
    logger = logging.getLogger(__name__)
    
    session_id = state.get("session_id") or state.get("context", {}).get("thread_id", "default")
    context_parts = []
    
    # Try to get Huginn state
    try:
        from src.norns.memory_tools import _huginn
        if _huginn:
            perception = _huginn.perceive(session_id)
            if perception and perception.flags:
                context_parts.append(f"## Active Flags: {', '.join(perception.flags)}")
    except Exception as e:
        logger.debug(f"Huginn context unavailable: {e}")
    
    # Try to get Frigg persona
    try:
        from src.norns.memory_tools import _frigg
        if _frigg:
            persona = _frigg.divine(session_id)
            if persona and persona.tags:
                context_parts.append(f"## User Tags: {', '.join(persona.tags)}")
    except Exception as e:
        logger.debug(f"Frigg context unavailable: {e}")
    
    # Try to recall relevant memories for the current query
    try:
        from src.norns.memory_tools import _muninn
        if _muninn:
            # Get the last human message
            last_human = None
            for msg in reversed(state.get("messages", [])):
                if isinstance(msg, HumanMessage):
                    last_human = extract_text_content(msg.content)
                    break
            
            if last_human and len(last_human) > 10:
                # Use a new event loop for thread-safety in ThreadPoolExecutor
                loop = asyncio.new_event_loop()
                try:
                    memories = loop.run_until_complete(_muninn.recall(last_human, k=3))
                    if memories:
                        mem_summaries = [f"- {m.content[:100]}..." for m in memories[:3]]
                        context_parts.append(f"## Relevant Memories:\n" + "\n".join(mem_summaries))
                finally:
                    loop.close()
    except Exception as e:
        logger.debug(f"Muninn context unavailable: {e}")
    
    return "\n\n".join(context_parts) if context_parts else ""


def trim_messages(messages: list, max_messages: int = 20, max_tool_results: int = 500) -> list:
    """
    Trim conversation history to stay within context limits.
    
    - Keeps system message
    - Keeps last max_messages exchanges  
    - Truncates long tool results
    """
    from langchain_core.messages import ToolMessage
    
    if len(messages) <= max_messages:
        # Just truncate tool results
        trimmed = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                content = str(msg.content) if msg.content else ""
                if len(content) > max_tool_results:
                    # Truncate long tool results
                    msg = ToolMessage(
                        content=content[:max_tool_results] + "... [truncated]",
                        tool_call_id=msg.tool_call_id
                    )
            trimmed.append(msg)
        return trimmed
    
    # Keep system message + last N messages
    trimmed = []
    if messages and isinstance(messages[0], SystemMessage):
        trimmed.append(messages[0])
        messages = messages[1:]
    
    # Take last max_messages, truncating tool results
    for msg in messages[-max_messages:]:
        if isinstance(msg, ToolMessage):
            content = str(msg.content) if msg.content else ""
            if len(content) > max_tool_results:
                msg = ToolMessage(
                    content=content[:max_tool_results] + "... [truncated]",
                    tool_call_id=msg.tool_call_id
                )
        trimmed.append(msg)
    
    return trimmed


def norns_node(state: NornState) -> NornState:
    from langchain_core.messages import ToolMessage, HumanMessage
    from src.norns.memory_tools import skills_retrieve
    
    # Trim messages to avoid context overflow
    conversation = trim_messages(list(state["messages"]))
    
    # Two-pass cleaning to handle tool_calls/ToolMessage mismatches
    # Pass 1: Identify which tool_call_ids have responses
    tool_call_ids_with_responses = set()
    for msg in conversation:
        if isinstance(msg, ToolMessage) and hasattr(msg, 'tool_call_id'):
            tool_call_ids_with_responses.add(msg.tool_call_id)
    
    # RAG: Retrieve relevant skills based on current user query
    skills_context = ""
    try:
        # Extract the most recent user message as context for skill retrieval
        user_messages = [msg for msg in reversed(conversation) if isinstance(msg, HumanMessage)]
        if user_messages:
            # Handle multimodal content format (list of content blocks) vs plain string
            raw_content = user_messages[0].content
            if isinstance(raw_content, list):
                # Extract text from content blocks like [{'type': 'text', 'text': '...'}]
                text_parts = []
                for block in raw_content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                latest_query = " ".join(text_parts)
            else:
                latest_query = str(raw_content) if raw_content else ""
            
            # skills_retrieve is a StructuredTool, use ainvoke with dict args
            # Use a new event loop for thread-safety in ThreadPoolExecutor
            loop = asyncio.new_event_loop()
            try:
                skills = loop.run_until_complete(skills_retrieve.ainvoke({
                    "query": latest_query[:500],  # Truncate long queries
                    "role": "sre",  # Default role, can be made dynamic based on context
                    "k": 3
                }))
                
                if skills and not (isinstance(skills, dict) and "error" in skills):
                    skills_context = "\n\n## 🛠️ Relevant Skills for This Task\n\n"
                    for skill in skills:
                        name = skill.get("name", "unknown")
                        summary = skill.get("summary", "")
                        content = skill.get("content", "")
                        
                        skills_context += f"### {name}\n"
                        if summary:
                            skills_context += f"_{summary}_\n\n"
                        skills_context += f"{content[:1000]}\n\n"  # Limit content size
                        skills_context += "---\n\n"
                    
                    logger.info(f"Retrieved {len(skills)} relevant skills for Norns")
            finally:
                loop.close()
    except Exception as e:
        logger.warning(f"Skills retrieval failed in norns_node: {e}")
    
    # Pass 2: Clean conversation - remove orphaned messages on both sides
    cleaned_conversation = []
    for i, msg in enumerate(conversation):
        if isinstance(msg, ToolMessage):
            # Only include if there's a preceding AIMessage with this tool_call_id
            has_matching_call = False
            for prev_msg in reversed(cleaned_conversation):
                if hasattr(prev_msg, 'tool_calls') and prev_msg.tool_calls:
                    for tc in prev_msg.tool_calls:
                        if tc.get('id') == msg.tool_call_id:
                            has_matching_call = True
                            break
                    if has_matching_call:
                        break
            if has_matching_call:
                cleaned_conversation.append(msg)
            # Otherwise skip this orphaned ToolMessage
        elif hasattr(msg, 'tool_calls') and msg.tool_calls:
            # AIMessage with tool_calls - check if ALL tool_calls have responses
            all_have_responses = all(
                tc.get('id') in tool_call_ids_with_responses 
                for tc in msg.tool_calls
            )
            if all_have_responses:
                # All tool calls have responses - include this message
                cleaned_conversation.append(msg)
            else:
                # Some tool calls don't have responses - convert to plain AIMessage
                # This prevents the "tool_calls must be followed by tool messages" error
                plain_content = extract_text_content(msg.content) if msg.content else ""
                if plain_content:
                    # Create a new AIMessage without tool_calls
                    cleaned_conversation.append(AIMessage(content=plain_content))
                # If no content, just skip this message entirely
        else:
            cleaned_conversation.append(msg)
    
    conversation = cleaned_conversation
    
    # Build cognitive context
    cognitive_ctx = state.get("cognitive_context") or _build_cognitive_context(state)
    
    # Inject RAG-retrieved skills into cognitive context
    if skills_context:
        cognitive_ctx = (cognitive_ctx or "") + skills_context
    
    # Build full system prompt with cognitive context and todos
    todo_overview = format_todo_overview(state.get('todos', []))
    
    full_system_prompt = NORNS_SYSTEM_PROMPT
    if cognitive_ctx:
        full_system_prompt += f"\n\n# Current Context\n{cognitive_ctx}"
    if todo_overview:
        full_system_prompt += f"\n\n## Current TODOs:\n{todo_overview}"
    
    # Add system prompt if not present or update existing
    if not conversation or not isinstance(conversation[0], SystemMessage):
        conversation = [SystemMessage(content=full_system_prompt)] + conversation
    else:
        conversation[0] = SystemMessage(content=full_system_prompt)
    
    # Get LLM from database configuration
    llm = create_llm()
    
    response = llm.invoke(conversation)
    
    # With add_messages reducer, only return new messages (not full list)
    return {
        "messages": [response],
        "current_norn": determine_norn(response.content),
        "context": state.get("context", {}),
        "todos": state.get("todos", []),
        "session_id": state.get("session_id", ""),
        "cognitive_context": cognitive_ctx,
    }


def should_continue(state: NornState) -> Literal["tools", "end"]:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "end"


async def persist_turn_node(state: NornState) -> NornState:
    """
    Persist the conversation turn to Muninn (long-term memory).
    This runs after each successful agent response.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from src.norns.memory_tools import _muninn, _huginn, _frigg
        
        session_id = state.get("session_id") or state.get("context", {}).get("thread_id", "default")
        
        # Get the last human message and AI response
        messages = state.get("messages", [])
        last_human = None
        last_ai = None
        
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and last_ai is None:
                last_ai = msg
            elif isinstance(msg, HumanMessage) and last_human is None:
                last_human = msg
            if last_human and last_ai:
                break
        
        # Store the turn in Muninn (episodic memory)
        if _muninn and last_human and last_ai:
            human_content = extract_text_content(last_human.content)
            ai_content = extract_text_content(last_ai.content)
            
            # Store as episodic memory
            from src.memory.muninn.store import MemoryFragment, MemoryType
            turn_content = f"User: {human_content}\n\nNorns: {ai_content}"
            
            fragment = MemoryFragment(
                type=MemoryType.EPISODIC,
                content=turn_content,
                domain="conversation",
                topic="norns_chat",
                session_id=session_id,
            )
            
            try:
                await _muninn.remember(fragment)
                logger.debug(f"Persisted turn to Muninn for session {session_id}")
            except Exception as e:
                logger.warning(f"Failed to persist to Muninn: {e}")
        
        # Update Huginn state
        if _huginn and last_human:
            try:
                await _huginn.observe_turn(
                    session_id=session_id,
                    user_id=session_id,  # Use session as user for now
                    utterance=extract_text_content(last_human.content),
                )
                logger.debug(f"Updated Huginn state for session {session_id}")
            except Exception as e:
                logger.warning(f"Failed to update Huginn: {e}")
        
        # Track user with Frigg (update tags to ensure persona exists)
        if _frigg:
            try:
                persona = _frigg.divine(session_id)
                if not persona:
                    # Initialize persona by updating tags
                    await _frigg.update_tags(session_id, "norns_user", "active")
                    logger.debug(f"Initialized Frigg persona for session {session_id}")
            except Exception as e:
                logger.debug(f"Frigg persona check: {e}")
                
    except Exception as e:
        # Don't fail the turn if persistence fails
        import logging
        logging.getLogger(__name__).warning(f"Turn persistence failed: {e}")
    
    return state


async def recover_context_node(state: NornState) -> NornState:
    """
    Recover conversation context from Muninn if state seems empty.
    This helps recover from errors that corrupted the state.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    messages = state.get("messages", [])
    
    # If we have messages, no recovery needed
    if len(messages) > 1:  # More than just the current message
        return state
    
    try:
        from src.norns.memory_tools import _muninn, _frigg
        
        session_id = state.get("session_id") or state.get("context", {}).get("thread_id", "default")
        
        # Try to recover recent conversation from Muninn
        if _muninn:
            memories = await _muninn.recall(
                query=f"conversation session:{session_id}",
                k=5,
                domain="conversation",
            )
            
            if memories:
                # Build context summary from recent memories
                context_summary = "## Recent Conversation History (recovered from Muninn)\n"
                for mem in memories[:3]:  # Last 3 turns
                    context_summary += f"\n{mem.content[:500]}\n---"
                
                # Add to state cognitive context
                existing_ctx = state.get("cognitive_context", "")
                state["cognitive_context"] = f"{existing_ctx}\n\n{context_summary}"
                logger.info(f"Recovered {len(memories)} turns from Muninn")
        
        # Get user context from Frigg
        if _frigg:
            persona = _frigg.divine(session_id)
            if persona:
                state["cognitive_context"] = (
                    state.get("cognitive_context", "") + 
                    f"\n\n## User Context (Frigg)\nTags: {', '.join(persona.tags or [])}"
                )
                
    except Exception as e:
        logger.warning(f"Context recovery failed: {e}")
    
    return state


def create_norns_graph(use_checkpointer: bool = False):
    """Create the Norns graph.
    
    Args:
        use_checkpointer: If True, use MemorySaver for local persistence.
                         If False (default), let LangGraph API handle persistence.
    
    Graph flow:
        entry -> recover_context -> gate -> (plan | chat)
                                         -> norns -> (tools | persist -> end)
                                                      ↑______|
    """
    workflow = StateGraph(NornState)
    
    # Recovery node - hydrates context from Muninn if state is empty
    workflow.add_node("recover_context", recover_context_node)
    
    # Router gate
    workflow.add_node("gate", lambda x: x)
    
    # Core nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("norns", norns_node)
    workflow.add_node("tools", ToolNode(NORN_TOOLS))
    
    # Persistence node - saves turn to Muninn after successful response
    workflow.add_node("persist_turn", persist_turn_node)
    
    # Entry point is now recovery
    workflow.set_entry_point("recover_context")
    workflow.add_edge("recover_context", "gate")
    
    # Router decides plan vs chat
    workflow.add_conditional_edges("gate", router, {"plan": "planner", "chat": "norns"})
    workflow.add_edge("planner", "norns")
    
    # After norns: either tools (loop) or persist (end)
    def should_continue_or_persist(state: NornState) -> Literal["tools", "persist"]:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "persist"
    
    workflow.add_conditional_edges(
        "norns",
        should_continue_or_persist,
        {"tools": "tools", "persist": "persist_turn"},
    )
    workflow.add_edge("tools", "norns")
    workflow.add_edge("persist_turn", END)
    
    if use_checkpointer:
        return workflow.compile(checkpointer=MemorySaver())
    return workflow.compile()

# For LangGraph API - no custom checkpointer (API handles persistence)
NORN_GRAPH = create_norns_graph(use_checkpointer=False)


class NornsAgent:
    def __init__(self, session: Optional[str] = None):
        self.graph = create_norns_graph(use_checkpointer=True)
        self.session = session
        self.thread_id = f"norns-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        self.memory: Optional[RedisShortTermMemory] = get_short_term_memory()

    def _hydrate_state(self, message: str, thread_id: str) -> tuple[NornState, HumanMessage]:
        history: list[BaseMessage] = []
        todos: list[TodoItem] = []
        if self.memory:
            history = self.memory.load_messages(thread_id)
            todos = self.memory.load_todos(thread_id)
        human = HumanMessage(content=message)
        state: NornState = {
            "messages": history + [human],
            "current_norn": "verdandi",
            "context": {"session": self.session, "thread_id": thread_id},
            "todos": todos,
            "session_id": thread_id,
        }
        llm_config = _get_session_llm_config(thread_id)
        if llm_config:
            state["llm_config"] = llm_config
        return state, human

    async def chat(self, message: str, thread_id: Optional[str] = None) -> str:
        thread = thread_id or self.thread_id
        state, human = self._hydrate_state(message, thread)
        config = {"configurable": {"thread_id": thread}}
        result = await self.graph.ainvoke(state, config)
        ai_response = next(
            (msg for msg in reversed(result["messages"]) if isinstance(msg, AIMessage)),
            None,
        )
        if ai_response is None:
            return "The Norns are silent..."
        if self.memory:
            self.memory.append_messages(thread, [human, ai_response])
            self.memory.save_todos(thread, result.get("todos", []))
        return ai_response.content

    def chat_sync(self, message: str, thread_id: Optional[str] = None) -> str:
        import asyncio

        return asyncio.run(self.chat(message, thread_id))

    async def stream(self, message: str, thread_id: Optional[str] = None):
        thread = thread_id or self.thread_id
        state, human = self._hydrate_state(message, thread)
        config = {"configurable": {"thread_id": thread}}

        buffer = ""
        final_todos = state.get("todos", [])

        async for event in self.graph.astream_events(state, config, version="v1"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    buffer += chunk.content
                    yield chunk.content
            if event["event"] in {"on_graph_end", "on_chain_end"}:
                output = event["data"].get("output") or event["data"].get("state")
                if output and isinstance(output, dict):
                    final_todos = output.get("todos", final_todos)

        if self.memory and buffer:
            self.memory.append_messages(thread, [human, AIMessage(content=buffer)])
            self.memory.save_todos(thread, final_todos)


async def ask_the_norns(question: str, session: Optional[str] = None) -> str:
    agent = NornsAgent(session=session)
    return await agent.chat(question)


# =============================================================================
# Cognitive Architecture Initialization
# =============================================================================

def _initialize_cognitive_components():
    """
    Initialize Raven cognitive memory components.
    
    This sets up:
    - Huginn (state) with Redis
    - Muninn (memory) with local index
    - Hel (governance) weight engine
    - Frigg (context) with Muninn integration
    - Mímir (domain) dossier loader
    - Ollama (local LLM) provider
    """
    import logging
    import os
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    # Track initialization status
    init_status = {
        "huginn": False,
        "muninn": False,
        "hel": False,
        "frigg": False,
        "mimir": False,
        "ollama": False,
        "skills_indexed": False,
    }
    
    try:
        from src.norns.memory_tools import init_memory_tools
        
        # Initialize Huginn (State Agent) - requires Redis
        huginn = None
        try:
            from src.memory.huginn import HuginnStateAgent
            redis_url = str(settings.REDIS_URL) if settings.REDIS_URL else "redis://redis:6379"
            huginn = HuginnStateAgent(
                redis_url=redis_url,
                kafka_bootstrap=settings.KAFKA_BOOTSTRAP,
            )
            
            # Validate Redis connection (non-blocking check)
            loop = asyncio.new_event_loop()
            try:
                async def _check_redis():
                    try:
                        r = await huginn._get_redis()
                        await r.ping()
                        return True
                    except Exception:
                        return False
                
                redis_ok = loop.run_until_complete(_check_redis())
                if redis_ok:
                    init_status["huginn"] = True
                    logger.info(f"✓ Huginn (State) initialized with Redis at {redis_url}")
                else:
                    logger.warning(f"✗ Huginn: Redis not reachable at {redis_url} - state caching will be local only")
            finally:
                loop.close()
                
        except ImportError as e:
            logger.warning(f"Huginn import failed (redis.asyncio): {e}")
        except Exception as e:
            logger.warning(f"Huginn not initialized: {e}")
        
        # Initialize Muninn (Memory Store) - core component
        muninn = None
        try:
            from src.memory.muninn import MuninnStore
            database_url = str(settings.DATABASE_URL) if settings.DATABASE_URL else None
            muninn = MuninnStore(database_url=database_url)
            init_status["muninn"] = True
            
            # Log index size for monitoring
            index_size = len(muninn._memory_index) if hasattr(muninn, '_memory_index') else 0
            logger.info(f"✓ Muninn (Memory) initialized (index_size={index_size}, db={'connected' if database_url else 'local-only'})")
        except ImportError as e:
            logger.warning(f"Muninn import failed: {e}")
        except Exception as e:
            logger.warning(f"Muninn not initialized: {e}")
        
        # Initialize Hel (Weight Engine) - memory governance
        hel = None
        try:
            from src.memory.hel import HelWeightEngine
            hel = HelWeightEngine()
            
            # Validate Hel's decay curve is configured
            if hasattr(hel, 'decay_rate'):
                init_status["hel"] = True
                logger.info(f"✓ Hel (Governance) initialized (decay_rate={getattr(hel, 'decay_rate', 'default')})")
            else:
                init_status["hel"] = True
                logger.info("✓ Hel (Governance) initialized with defaults")
        except ImportError as e:
            logger.warning(f"Hel import failed: {e}")
        except Exception as e:
            logger.warning(f"Hel not initialized: {e}")
        
        # Initialize Frigg (Context Agent) - depends on Muninn
        frigg = None
        try:
            from src.memory.frigg import FriggContextAgent
            frigg = FriggContextAgent(
                muninn=muninn,  # Pass Muninn for memory integration
                kafka_bootstrap=settings.KAFKA_BOOTSTRAP,
            )
            
            if muninn:
                init_status["frigg"] = True
                logger.info("✓ Frigg (Context) initialized with Muninn integration")
            else:
                init_status["frigg"] = True
                logger.warning("⚠ Frigg (Context) initialized without Muninn - limited context capabilities")
        except ImportError as e:
            logger.warning(f"Frigg import failed: {e}")
        except Exception as e:
            logger.warning(f"Frigg not initialized: {e}")
        
        # Initialize Mímir (Domain Intelligence) - dossier loader
        mimir = None
        try:
            from src.memory.mimir import MimirDossierLoader, MimirTripletEngine
            
            # Try multiple dossier locations
            dossier_paths = [
                Path("/app/hlidskjalf/dossiers/ravenhelm"),
                Path("hlidskjalf/dossiers/ravenhelm"),
                Path(os.environ.get("HLIDSKJALF_WORKSPACE", ".")) / "hlidskjalf" / "dossiers" / "ravenhelm",
                Path(__file__).parent.parent.parent / "dossiers" / "ravenhelm",
            ]
            
            dossier_path = None
            for path in dossier_paths:
                if path.exists():
                    dossier_path = path
                    break
            
            if dossier_path:
                loader = MimirDossierLoader(dossier_path)
                dossier = loader.load_wisdom()
                mimir = MimirTripletEngine(dossier)
                init_status["mimir"] = True
                
                # Log loaded triplets for monitoring
                triplet_count = len(dossier.triplets) if hasattr(dossier, 'triplets') else 0
                logger.info(f"✓ Mímir (Domain) initialized with dossier '{dossier.name}' ({triplet_count} triplets)")
            else:
                logger.warning(f"✗ Mímir: No dossier found at any of: {[str(p) for p in dossier_paths[:2]]}")
        except ImportError as e:
            logger.warning(f"Mímir import failed: {e}")
        except Exception as e:
            logger.warning(f"Mímir not initialized: {e}")
        
        # Initialize Ollama (Local LLM)
        ollama = None
        try:
            ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
            from src.memory.ollama_provider import OllamaProvider
            ollama = OllamaProvider(base_url=ollama_url)
            
            # Check if Ollama is reachable (non-blocking)
            loop = asyncio.new_event_loop()
            try:
                import httpx
                async def _check_ollama():
                    try:
                        async with httpx.AsyncClient(timeout=5.0) as client:
                            resp = await client.get(f"{ollama_url}/api/tags")
                            return resp.status_code == 200
                    except Exception:
                        return False
                
                ollama_ok = loop.run_until_complete(_check_ollama())
                if ollama_ok:
                    init_status["ollama"] = True
                    logger.info(f"✓ Ollama provider configured and reachable at {ollama_url}")
                else:
                    logger.warning(f"⚠ Ollama configured at {ollama_url} but not reachable - local embeddings disabled")
            finally:
                loop.close()
        except ImportError as e:
            logger.warning(f"Ollama import failed (httpx): {e}")
        except Exception as e:
            logger.warning(f"Ollama not configured: {e}")
        
        # Index filesystem skills into Muninn (RAG skills corpus)
        if muninn:
            try:
                from src.norns.skills import migrate_skills_to_muninn
                loop = asyncio.new_event_loop()
                try:
                    skill_map = loop.run_until_complete(migrate_skills_to_muninn(muninn))
                    init_status["skills_indexed"] = True
                    logger.info(f"✓ Indexed {len(skill_map)} skills into Muninn")
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(f"Skill indexing failed: {e}")
        
        # Initialize memory tools with components
        init_memory_tools(
            huginn=huginn,
            frigg=frigg,
            muninn=muninn,
            hel=hel,
            mimir=mimir,
            ollama=ollama,
        )
        
        # Summary
        active = sum(1 for v in init_status.values() if v)
        total = len(init_status)
        logger.info(f"✓ Memory tools initialized ({active}/{total} components active)")
        
        if not init_status["muninn"]:
            logger.error("⚠ CRITICAL: Muninn (core memory) not initialized - memory tools severely degraded")
        
    except ImportError as e:
        logger.warning(f"Memory components not available: {e}")
    except Exception as e:
        logger.error(f"Failed to initialize cognitive components: {e}")


# Initialize on module load
_initialize_cognitive_components()


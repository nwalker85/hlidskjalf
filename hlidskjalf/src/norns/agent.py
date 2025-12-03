"""
The Norns Agent — LangGraph Deep Agent implementation.

The sisters maintain TODO lists, can manipulate the workspace, spawn specialists,
and persist short-term context in Redis.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver

# Optional HuggingFace TGI support
try:
    from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False
from langgraph.graph import END, StateGraph, add_messages
from langgraph.prebuilt import ToolNode

from src.core.config import get_settings
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


def _get_session_llm_config(session_id: str) -> dict | None:
    """
    Get LLM configuration from Huginn state for a session.
    
    Returns dict with 'reasoning', 'tools', 'subagents' keys,
    or None if no config is set.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from src.norns.memory_tools import _huginn
        if _huginn:
            state = _huginn.perceive(session_id)
            if state and hasattr(state, 'llm_config') and state.llm_config:
                config = state.llm_config
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
    except Exception as e:
        logger.debug(f"Could not get LLM config from Huginn: {e}")
    
    return None

# Compact instructions to reduce context window usage
REASONING_INSTRUCTIONS = """Think step-by-step. Use tools to gather info before answering."""

TODO_INSTRUCTIONS = """Use write_todos for complex multi-step work."""

SKILLS_INSTRUCTIONS = """search_skills(query) to find solutions. create_skill() for novel ones."""

COGNITIVE_ARCHITECTURE_INSTRUCTIONS = """## Memory: muninn_recall(query) FIRST, muninn_remember(content) to save."""

SELF_AWARENESS_INSTRUCTIONS = """## Workspace: /app (container) = ~/Development/hlidskjalf (host). Use workspace_* tools."""

PROBLEM_SOLVING_INSTRUCTIONS = """## Tools: workspace_list/read/write for files. execute_terminal_command for shell/docker/git."""

def build_norns_system_prompt() -> str:
    """Build a COMPACT system prompt to save context window space."""
    return f"""# Norns Assistant

You help with the Ravenhelm platform. Be concise.

{SELF_AWARENESS_INSTRUCTIONS}
{PROBLEM_SOLVING_INSTRUCTIONS}
{COGNITIVE_ARCHITECTURE_INSTRUCTIONS}
{SKILLS_INSTRUCTIONS}
{TODO_INSTRUCTIONS}

Keep responses brief. Use tools to gather info before answering."""

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


def create_llm_from_config(
    provider: str = "ollama",
    model: str = "mistral-nemo:latest",
    temperature: float = 0.7,
    bind_tools: bool = True
):
    """
    Create an LLM from explicit configuration.
    
    This is used for dynamic runtime model switching based on Huginn state.
    
    Args:
        provider: Provider name (ollama, lmstudio, openai, huggingface)
        model: Model identifier
        temperature: Temperature for generation
        bind_tools: Whether to bind tools to the LLM
    """
    import logging
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    provider = provider.lower()
    
    if provider == "lmstudio":
        logger.debug(f"Creating LM Studio LLM: {model}")
        llm = ChatOpenAI(
            model=model,
            base_url=settings.LMSTUDIO_URL,
            api_key="lm-studio",
            temperature=temperature,
        )
    elif provider == "huggingface" and HF_AVAILABLE:
        logger.debug(f"Creating HuggingFace LLM at {settings.HUGGINGFACE_TGI_URL}")
        llm_endpoint = HuggingFaceEndpoint(
            endpoint_url=f"{settings.HUGGINGFACE_TGI_URL}/generate",
            max_new_tokens=4096,
            temperature=temperature,
            huggingfacehub_api_token=settings.HUGGING_FACE_HUB_TOKEN or None,
        )
        llm = ChatHuggingFace(llm=llm_endpoint)
    elif provider == "openai":
        logger.debug(f"Creating OpenAI LLM: {model}")
        llm = ChatOpenAI(
            model=model,
            temperature=temperature,
        )
    else:
        # Default: Ollama
        logger.debug(f"Creating Ollama LLM: {model}")
        llm = ChatOllama(
            model=model,
            base_url=settings.OLLAMA_URL,
            temperature=temperature,
        )
    
    if bind_tools:
        return llm.bind_tools(NORN_TOOLS)
    return llm


def get_llm_for_purpose(purpose: str, session_config: dict):
    """
    Get the appropriate LLM for a specific purpose based on session config.
    
    Args:
        purpose: One of 'reasoning', 'tools', 'subagents'
        session_config: LLM configuration dict from Huginn state
        
    Returns:
        LLM instance configured for the purpose
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Get config for purpose, fallback to defaults
    config = session_config.get(purpose, {})
    provider = config.get("provider", "ollama")
    model = config.get("model", "mistral-nemo:latest")
    temperature = config.get("temperature", 0.7 if purpose == "reasoning" else 0.1)
    
    logger.debug(f"LLM for {purpose}: {provider}/{model} @ temp={temperature}")
    
    # Reasoning needs tools, others don't necessarily
    bind_tools = purpose == "reasoning"
    
    return create_llm_from_config(
        provider=provider,
        model=model,
        temperature=temperature,
        bind_tools=bind_tools,
    )


def create_llm(use_local: bool = True):
    """
    Create the LLM for the Norns.
    
    Supports four providers (configured via LLM_PROVIDER setting):
    - 'ollama': Local Ollama server (default)
    - 'lmstudio': LM Studio with OpenAI-compatible API
    - 'huggingface': HuggingFace Text Generation Inference
    - 'openai': OpenAI API (subject to rate limits)
    
    Args:
        use_local: If True (default), use local provider. If False, use OpenAI.
    """
    import os
    import logging
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    # Check for explicit override via environment
    provider = os.environ.get("LLM_PROVIDER", settings.LLM_PROVIDER).lower()
    use_openai = os.environ.get("NORNS_USE_OPENAI", "false").lower() == "true"
    
    if use_openai:
        provider = "openai"
    
    if provider == "lmstudio":
        # Use LM Studio - OpenAI-compatible API, local, no rate limits
        logger.info(f"Using LM Studio at {settings.LMSTUDIO_URL} with model {settings.LMSTUDIO_MODEL}")
        llm = ChatOpenAI(
            model=settings.LMSTUDIO_MODEL,
            base_url=settings.LMSTUDIO_URL,
            api_key="lm-studio",  # LM Studio doesn't require a real key
            temperature=settings.NORNS_TEMPERATURE,
        )
    elif provider == "huggingface" and HF_AVAILABLE:
        # Use HuggingFace TGI - local, no rate limits
        logger.info(f"Using HuggingFace TGI at {settings.HUGGINGFACE_TGI_URL}")
        llm_endpoint = HuggingFaceEndpoint(
            endpoint_url=f"{settings.HUGGINGFACE_TGI_URL}/generate",
            max_new_tokens=4096,
            temperature=settings.NORNS_TEMPERATURE,
            huggingfacehub_api_token=settings.HUGGING_FACE_HUB_TOKEN or None,
        )
        llm = ChatHuggingFace(llm=llm_endpoint)
    elif provider == "huggingface" and not HF_AVAILABLE:
        logger.warning("HuggingFace requested but langchain_huggingface not installed, falling back to Ollama")
        llm = ChatOllama(
            model=settings.OLLAMA_CHAT_MODEL,
            base_url=settings.OLLAMA_URL,
            temperature=settings.NORNS_TEMPERATURE,
        )
    elif provider == "openai" or not use_local:
        # Use OpenAI (subject to rate limits)
        logger.info(f"Using OpenAI model {settings.NORNS_MODEL}")
        llm = ChatOpenAI(
            model=settings.NORNS_MODEL, 
            temperature=settings.NORNS_TEMPERATURE
        )
    else:
        # Default: Use local Ollama - no rate limits, no API costs
        logger.info(f"Using Ollama model {settings.OLLAMA_CHAT_MODEL}")
        llm = ChatOllama(
            model=settings.OLLAMA_CHAT_MODEL,
            base_url=settings.OLLAMA_URL,
            temperature=settings.NORNS_TEMPERATURE,
        )
    
    return llm.bind_tools(NORN_TOOLS)


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
                # Synchronously check memory index (no await needed for local index)
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Can't await in sync context with running loop
                        pass
                    else:
                        memories = asyncio.run(_muninn.recall(last_human, k=3))
                        if memories:
                            mem_summaries = [f"- {m.content[:100]}..." for m in memories[:3]]
                            context_parts.append(f"## Relevant Memories:\n" + "\n".join(mem_summaries))
                except RuntimeError:
                    pass  # Skip if no event loop
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
    from langchain_core.messages import ToolMessage
    
    # Trim messages to avoid context overflow
    conversation = trim_messages(list(state["messages"]))
    
    # Two-pass cleaning to handle tool_calls/ToolMessage mismatches
    # Pass 1: Identify which tool_call_ids have responses
    tool_call_ids_with_responses = set()
    for msg in conversation:
        if isinstance(msg, ToolMessage) and hasattr(msg, 'tool_call_id'):
            tool_call_ids_with_responses.add(msg.tool_call_id)
    
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
    
    # Get LLM config from Huginn state for dynamic model selection
    session_id = state.get("session_id") or state.get("context", {}).get("thread_id", "default")
    llm_config = _get_session_llm_config(session_id)
    
    if llm_config:
        # Use session-specific config for reasoning
        llm = get_llm_for_purpose("reasoning", llm_config)
    else:
        # Fallback to default config
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
        }
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
    - Mímir (domain) dossier loader
    """
    import logging
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    try:
        from src.norns.memory_tools import init_memory_tools
        
        # Initialize Huginn (State Agent)
        huginn = None
        try:
            from src.memory.huginn import HuginnStateAgent
            huginn = HuginnStateAgent(
                redis_url=settings.REDIS_URL or "redis://redis:6379",
            )
            logger.info("✓ Huginn (State) initialized")
        except Exception as e:
            logger.warning(f"Huginn not initialized: {e}")
        
        # Initialize Muninn (Memory Store)
        muninn = None
        try:
            from src.memory.muninn import MuninnStore
            muninn = MuninnStore()  # Uses local index, database optional
            logger.info("✓ Muninn (Memory) initialized")
        except Exception as e:
            logger.warning(f"Muninn not initialized: {e}")
        
        # Initialize Hel (Weight Engine)
        hel = None
        try:
            from src.memory.hel import HelWeightEngine
            hel = HelWeightEngine()
            logger.info("✓ Hel (Governance) initialized")
        except Exception as e:
            logger.warning(f"Hel not initialized: {e}")
        
        # Initialize Frigg (Context Agent)
        frigg = None
        try:
            from src.memory.frigg import FriggContextAgent
            frigg = FriggContextAgent(muninn=muninn)
            logger.info("✓ Frigg (Context) initialized")
        except Exception as e:
            logger.warning(f"Frigg not initialized: {e}")
        
        # Initialize Mímir (Domain Intelligence)
        mimir = None
        try:
            from src.memory.mimir import MimirDossierLoader, MimirTripletEngine
            dossier_path = Path("/app/hlidskjalf/dossiers/ravenhelm")
            if not dossier_path.exists():
                dossier_path = Path("hlidskjalf/dossiers/ravenhelm")
            
            if dossier_path.exists():
                loader = MimirDossierLoader(dossier_path)
                dossier = loader.load_wisdom()
                mimir = MimirTripletEngine(dossier)
                logger.info(f"✓ Mímir (Domain) initialized with dossier: {dossier.name}")
            else:
                logger.warning(f"Dossier not found at {dossier_path}")
        except Exception as e:
            logger.warning(f"Mímir not initialized: {e}")
        
        # Initialize Ollama (Local LLM)
        ollama = None
        try:
            import os
            ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
            from src.memory.ollama_provider import OllamaProvider
            ollama = OllamaProvider(base_url=ollama_url)
            # Don't await initialization here, let it lazy-load
            logger.info(f"✓ Ollama provider configured at {ollama_url}")
        except Exception as e:
            logger.warning(f"Ollama not configured: {e}")
        
        # Initialize memory tools with components
        init_memory_tools(
            huginn=huginn,
            frigg=frigg,
            muninn=muninn,
            hel=hel,
            mimir=mimir,
            ollama=ollama,
        )
        logger.info("✓ Memory tools initialized")
        
    except ImportError as e:
        logger.warning(f"Memory components not available: {e}")
    except Exception as e:
        logger.error(f"Failed to initialize cognitive components: {e}")


# Initialize on module load
_initialize_cognitive_components()


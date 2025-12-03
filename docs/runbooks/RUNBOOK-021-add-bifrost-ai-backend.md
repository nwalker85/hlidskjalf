# RUNBOOK-021: Add a New Bifrost AI Backend

## Overview

This runbook describes how to add a new AI backend to Bifrost Gateway.
Bifrost uses an extensible backend pattern that allows different AI systems
to be plugged in with minimal changes to the core system.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BIFROST GATEWAY                               │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    MESSAGING ADAPTERS                        │   │
│  │  Telegram │ Slack │ Discord │ Matrix │ ...                  │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                       │
│                             ▼                                       │
│              ┌──────────────────────────────┐                      │
│              │      Message Handler         │                      │
│              │   (routes to AI backend)     │                      │
│              └──────────────┬───────────────┘                      │
│                             │                                       │
│                             ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      AI BACKENDS                             │   │
│  │  ┌─────────┐ ┌─────────┐ ┌───────────┐ ┌─────────┐         │   │
│  │  │  Norns  │ │ OpenAI  │ │ Anthropic │ │   MCP   │  ...    │   │
│  │  └─────────┘ └─────────┘ └───────────┘ └─────────┘         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Available Backends

| Backend | Status | Description |
|---------|--------|-------------|
| `norns` | ✅ Ready | Hliðskjálf Norns via LangGraph API |
| `openai` | ✅ Ready | Direct OpenAI GPT models |
| `anthropic` | ✅ Ready | Direct Anthropic Claude models |
| `mcp` | ✅ Ready | Any MCP-compatible server |

## Quick Switch Between Backends

Change the `AI_BACKEND` environment variable:

```bash
# Use Norns (default)
AI_BACKEND=norns

# Use OpenAI directly
AI_BACKEND=openai
OPENAI_API_KEY=sk-...

# Use Claude directly
AI_BACKEND=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Use MCP server
AI_BACKEND=mcp
MCP_SERVER_URL=http://localhost:3000
```

## Adding a New Backend

### Step 1: Create the Backend File

Create `bifrost-gateway/src/backends/mybackend.py`:

```python
"""
MyBackend — Integration with MyAI API.
"""

from typing import AsyncIterator, Optional
import structlog

from src.backends.base import (
    BaseBackend,
    BackendCapabilities,
    BackendConfig,
    ChatRequest,
    ChatResponse,
)
from src.backends.registry import register_backend

logger = structlog.get_logger(__name__)


@register_backend("mybackend")  # Unique name
class MyBackend(BaseBackend):
    """
    Backend for MyAI system.
    
    Document what this backend connects to.
    """
    
    @property
    def name(self) -> str:
        return "mybackend"
    
    @property
    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_streaming=True,
            supports_threads=True,
            supports_tools=True,
            supports_vision=False,
            supports_files=False,
            supports_system_prompt=True,
            supports_message_history=True,
            max_context_tokens=128000,
            supports_structured_output=False,
            supports_function_calling=True,
        )
    
    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._client = None
    
    async def initialize(self) -> None:
        """Initialize the backend client."""
        if not self.config.api_key:
            logger.warning("mybackend_no_api_key")
            return
        
        # Initialize your client
        # self._client = MyAIClient(api_key=self.config.api_key)
        
        self._initialized = True
        logger.info("mybackend_initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the client."""
        # Cleanup
        self._client = None
        self._initialized = False
        logger.info("mybackend_shutdown")
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a message and get a response."""
        if not self._client:
            return ChatResponse(
                content="⚠️ Backend not initialized.",
                thread_id=request.thread_id or "error",
            )
        
        try:
            # Call your AI API
            # response = await self._client.chat(
            #     message=request.message,
            #     system=self.config.system_prompt,
            # )
            
            return ChatResponse(
                content="Response from MyAI",
                thread_id=request.thread_id or "new-thread",
                model="myai-model",
            )
            
        except Exception as e:
            logger.error("mybackend_chat_failed", error=str(e))
            return ChatResponse(
                content=f"⚠️ MyAI error: {e}",
                thread_id=request.thread_id or "error",
            )
    
    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Stream a response token by token."""
        if not self._client:
            yield "⚠️ Backend not initialized."
            return
        
        try:
            # Stream from your API
            # async for chunk in self._client.stream(request.message):
            #     yield chunk
            yield "Streaming response..."
                    
        except Exception as e:
            logger.error("mybackend_stream_failed", error=str(e))
            yield f"⚠️ Streaming error: {e}"
```

### Step 2: Register for Auto-Import

Edit `bifrost-gateway/src/backends/registry.py`:

```python
def _auto_register_backends():
    # ... existing imports ...
    
    try:
        from src.backends import mybackend  # noqa: F401
        logger.debug("loaded_backend_module", module="mybackend")
    except ImportError as e:
        logger.warning("backend_import_failed", module="mybackend", error=str(e))
```

### Step 3: Add Configuration

Edit `bifrost-gateway/src/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # =========================================================================
    # MYBACKEND
    # =========================================================================
    MYBACKEND_API_KEY: Optional[str] = None
    MYBACKEND_API_URL: Optional[str] = None
    MYBACKEND_MODEL: str = "myai-default"
    
    def get_mybackend_config(self) -> BackendConfig:
        """Get MyBackend configuration."""
        return BackendConfig(
            name="mybackend",
            enabled=self.AI_BACKEND == "mybackend" and bool(self.MYBACKEND_API_KEY),
            api_key=self.MYBACKEND_API_KEY,
            api_url=self.MYBACKEND_API_URL,
            model=self.MYBACKEND_MODEL,
            system_prompt=self.SYSTEM_PROMPT,
        )
    
    def get_active_backend_config(self) -> BackendConfig:
        backend_configs = {
            # ... existing backends ...
            "mybackend": self.get_mybackend_config,
        }
        # ... rest of method ...
```

### Step 4: Add Dependencies (if needed)

Edit `pyproject.toml`:

```toml
dependencies = [
    # ... existing deps ...
    "myai-sdk>=1.0.0",
]
```

### Step 5: Update Docker Compose

```yaml
environment:
  - AI_BACKEND=${AI_BACKEND:-norns}
  - MYBACKEND_API_KEY=${MYBACKEND_API_KEY:-}
  - MYBACKEND_API_URL=${MYBACKEND_API_URL:-}
```

### Step 6: Test

```bash
# Build and run
docker-compose build
docker-compose up -d

# Check backend status
curl http://localhost:8050/backends

# Test direct chat
curl -X POST http://localhost:8050/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from test!"}'
```

## Backend Interface Reference

### Required Methods

| Method | Description |
|--------|-------------|
| `name` | Property returning unique backend name |
| `capabilities` | Property returning `BackendCapabilities` |
| `initialize()` | Async setup (connections, validation) |
| `shutdown()` | Async cleanup |
| `chat(request)` | Process message and return response |

### Optional Overrides

| Method | Default | Description |
|--------|---------|-------------|
| `stream(request)` | Calls `chat()` | Stream response tokens |
| `get_wisdom()` | Generic message | Get wisdom/greeting |
| `build_system_prompt(request)` | From config | Customize system prompt |
| `detect_response_persona(content)` | "assistant" | Detect persona/character |

### ChatRequest Fields

| Field | Type | Description |
|-------|------|-------------|
| `message` | str | The user's message |
| `thread_id` | str | Conversation thread ID |
| `message_history` | list | Previous messages |
| `user_id` | str | User identifier |
| `channel_id` | str | Channel/chat identifier |
| `adapter_name` | str | Source adapter |
| `system_prompt` | str | Override system prompt |
| `temperature` | float | Override temperature |
| `max_tokens` | int | Override max tokens |

### ChatResponse Fields

| Field | Type | Description |
|-------|------|-------------|
| `content` | str | The AI's response |
| `thread_id` | str | Thread ID (for continuity) |
| `model` | str | Model that generated response |
| `tokens_used` | int | Token count |
| `current_norn` | str | Persona (for Norns-style) |
| `tool_calls` | list | Any tool invocations |
| `raw_response` | dict | Raw API response |

### BackendCapabilities Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `supports_streaming` | bool | True | Can stream responses |
| `supports_threads` | bool | True | Native thread support |
| `supports_tools` | bool | True | Tool/function calling |
| `supports_vision` | bool | False | Image understanding |
| `supports_files` | bool | False | File processing |
| `supports_system_prompt` | bool | True | System prompt support |
| `supports_message_history` | bool | True | Multi-turn context |
| `max_context_tokens` | int | 128000 | Context window size |

## Using MCP Backend

The MCP backend allows connecting to any AI system that exposes an MCP server.

### MCP Server Requirements

Your MCP server should expose:

1. **Chat Tool** — Named `chat` (or configure via `MCP_CHAT_TOOL`)
   ```json
   {
     "name": "chat",
     "description": "Send a message to the AI",
     "inputSchema": {
       "type": "object",
       "properties": {
         "message": {"type": "string"},
         "thread_id": {"type": "string"},
         "system_prompt": {"type": "string"}
       },
       "required": ["message"]
     }
   }
   ```

2. **Tool Response Format**
   ```json
   {
     "content": [{"type": "text", "text": "AI response here"}],
     "thread_id": "thread-123"
   }
   ```

### Configuration

```bash
AI_BACKEND=mcp
MCP_SERVER_URL=http://localhost:3000
MCP_CHAT_TOOL=chat
MCP_USE_SSE=true
```

## Creating a Bifrost MCP Server

If you want to expose Bifrost itself as an MCP server (allowing other AI systems
to send messages through it), see the `mcp_server/` module (coming soon).

## Checklist

- [ ] Created backend file in `src/backends/`
- [ ] Implemented all required methods
- [ ] Used `@register_backend("name")` decorator
- [ ] Added auto-import in `registry.py`
- [ ] Added configuration in `config.py`
- [ ] Added to `get_active_backend_config()`
- [ ] Added dependencies to `pyproject.toml`
- [ ] Updated `docker-compose.yml`
- [ ] Tested backend initialization
- [ ] Tested chat functionality
- [ ] Tested streaming (if supported)

## Troubleshooting

### Backend not appearing in `/backends`?

1. Check import in `registry.py`
2. Verify `@register_backend` decorator
3. Check logs for import errors

### "Backend not initialized"?

1. Check `AI_BACKEND` is set correctly
2. Check required credentials are set
3. Look at initialization logs

### Wrong backend being used?

1. Verify `AI_BACKEND` environment variable
2. Only one backend is active at a time
3. Restart after changing `AI_BACKEND`

## Related Runbooks

- [RUNBOOK-020: Add Bifrost Adapter](./RUNBOOK-020-add-bifrost-adapter.md)
- [RUNBOOK-001: Deploy Docker Service](./RUNBOOK-001-deploy-docker-service.md)

---

*Last updated: 2024*


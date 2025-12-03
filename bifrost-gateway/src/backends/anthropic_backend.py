"""
Anthropic Backend — Direct integration with Claude API.

Use this backend to connect Bifrost directly to Anthropic's Claude models
without going through an intermediate agent system.
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

# Optional import
try:
    from anthropic import AsyncAnthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    logger.debug("anthropic_not_installed", hint="pip install anthropic")


DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant accessible via Bifrost Gateway.
Be concise, helpful, and friendly. Use markdown formatting when appropriate."""


@register_backend("anthropic")
class AnthropicBackend(BaseBackend):
    """
    Backend for direct Anthropic Claude API access.
    
    Configuration:
        api_key: Anthropic API key
        model: Model to use (default: claude-3-5-sonnet-20241022)
        temperature: Temperature setting (default: 0.7)
        max_tokens: Max tokens (default: 4096)
    """
    
    @property
    def name(self) -> str:
        return "anthropic"
    
    @property
    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_streaming=True,
            supports_threads=False,
            supports_tools=True,
            supports_vision=True,
            supports_files=True,  # Claude supports PDFs
            supports_system_prompt=True,
            supports_message_history=True,
            max_context_tokens=200000,
            supports_structured_output=True,
            supports_function_calling=True,
        )
    
    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._client: Optional["AsyncAnthropic"] = None
        
        # Default to latest Claude model
        if not config.model or config.model == "gpt-4o":
            config.model = "claude-sonnet-4-20250514"
    
    async def initialize(self) -> None:
        """Initialize the Anthropic client."""
        if not HAS_ANTHROPIC:
            logger.warning("anthropic_not_available", hint="pip install anthropic")
            return
        
        if not self.config.api_key:
            logger.warning("anthropic_no_api_key")
            return
        
        self._client = AsyncAnthropic(api_key=self.config.api_key)
        
        self._initialized = True
        logger.info("anthropic_backend_initialized", model=self.config.model)
    
    async def shutdown(self) -> None:
        """Shutdown the client."""
        # Anthropic client doesn't need explicit cleanup
        self._client = None
        self._initialized = False
        logger.info("anthropic_backend_shutdown")
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a message to Claude."""
        if not self._client:
            return ChatResponse(
                content="⚠️ Anthropic backend not initialized.",
                thread_id=request.thread_id or "error",
            )
        
        # Build messages (Anthropic format)
        messages = []
        
        # Message history
        if request.message_history:
            for msg in request.message_history:
                role = msg.get("role", "user")
                # Anthropic uses "user" and "assistant" only
                if role == "system":
                    continue  # System goes in separate param
                messages.append({
                    "role": role,
                    "content": msg.get("content", ""),
                })
        
        # Current message
        messages.append({"role": "user", "content": request.message})
        
        try:
            response = await self._client.messages.create(
                model=self.config.model,
                max_tokens=request.max_tokens or self.config.max_tokens,
                system=self.build_system_prompt(request),
                messages=messages,
            )
            
            # Extract text content
            content = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text
            
            return ChatResponse(
                content=content or "No response from Claude.",
                thread_id=request.thread_id or response.id,
                model=response.model,
                tokens_used=(response.usage.input_tokens + response.usage.output_tokens) if response.usage else None,
            )
            
        except Exception as e:
            logger.error("anthropic_chat_failed", error=str(e))
            return ChatResponse(
                content=f"⚠️ Claude error: {e}",
                thread_id=request.thread_id or "error",
            )
    
    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Stream a response from Claude."""
        if not self._client:
            yield "⚠️ Anthropic backend not initialized."
            return
        
        messages = []
        if request.message_history:
            for msg in request.message_history:
                role = msg.get("role", "user")
                if role == "system":
                    continue
                messages.append({
                    "role": role,
                    "content": msg.get("content", ""),
                })
        
        messages.append({"role": "user", "content": request.message})
        
        try:
            async with self._client.messages.stream(
                model=self.config.model,
                max_tokens=request.max_tokens or self.config.max_tokens,
                system=self.build_system_prompt(request),
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            logger.error("anthropic_stream_failed", error=str(e))
            yield f"⚠️ Claude streaming error: {e}"
    
    def build_system_prompt(self, request: ChatRequest) -> str:
        """Build system prompt for Claude."""
        return request.system_prompt or self.config.system_prompt or DEFAULT_SYSTEM_PROMPT


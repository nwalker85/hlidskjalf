"""
OpenAI Backend — Direct integration with OpenAI API.

Use this backend to connect Bifrost directly to OpenAI's GPT models
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

# Optional import - only if user wants to use this backend
try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.debug("openai_not_installed", hint="pip install openai")


DEFAULT_SYSTEM_PROMPT = """You are a helpful AI assistant accessible via Bifrost Gateway.
Be concise, helpful, and friendly. Use markdown formatting when appropriate."""


@register_backend("openai")
class OpenAIBackend(BaseBackend):
    """
    Backend for direct OpenAI API access.
    
    Configuration:
        api_key: OpenAI API key
        model: Model to use (default: gpt-4o)
        temperature: Temperature setting (default: 0.7)
        extra:
            organization: OpenAI organization ID
            base_url: Custom base URL (for Azure, etc.)
    """
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_streaming=True,
            supports_threads=False,  # OpenAI doesn't have native threads
            supports_tools=True,
            supports_vision=True,
            supports_files=False,
            supports_system_prompt=True,
            supports_message_history=True,
            max_context_tokens=128000,
            supports_structured_output=True,
            supports_function_calling=True,
        )
    
    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._client: Optional["AsyncOpenAI"] = None
    
    async def initialize(self) -> None:
        """Initialize the OpenAI client."""
        if not HAS_OPENAI:
            logger.warning("openai_not_available", hint="pip install openai")
            return
        
        if not self.config.api_key:
            logger.warning("openai_no_api_key")
            return
        
        self._client = AsyncOpenAI(
            api_key=self.config.api_key,
            organization=self.config.extra.get("organization"),
            base_url=self.config.extra.get("base_url"),
        )
        
        self._initialized = True
        logger.info("openai_backend_initialized", model=self.config.model)
    
    async def shutdown(self) -> None:
        """Shutdown the client."""
        if self._client:
            await self._client.close()
        self._initialized = False
        logger.info("openai_backend_shutdown")
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a message to OpenAI."""
        if not self._client:
            return ChatResponse(
                content="⚠️ OpenAI backend not initialized.",
                thread_id=request.thread_id or "error",
            )
        
        # Build messages
        messages = []
        
        # System prompt
        system_prompt = self.build_system_prompt(request)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Message history
        if request.message_history:
            messages.extend(request.message_history)
        
        # Current message
        messages.append({"role": "user", "content": request.message})
        
        try:
            response = await self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=request.temperature or self.config.temperature,
                max_tokens=request.max_tokens or self.config.max_tokens,
            )
            
            content = response.choices[0].message.content or ""
            
            return ChatResponse(
                content=content,
                thread_id=request.thread_id or response.id,
                model=response.model,
                tokens_used=response.usage.total_tokens if response.usage else None,
            )
            
        except Exception as e:
            logger.error("openai_chat_failed", error=str(e))
            return ChatResponse(
                content=f"⚠️ OpenAI error: {e}",
                thread_id=request.thread_id or "error",
            )
    
    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Stream a response from OpenAI."""
        if not self._client:
            yield "⚠️ OpenAI backend not initialized."
            return
        
        messages = []
        system_prompt = self.build_system_prompt(request)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        if request.message_history:
            messages.extend(request.message_history)
        
        messages.append({"role": "user", "content": request.message})
        
        try:
            stream = await self._client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=request.temperature or self.config.temperature,
                max_tokens=request.max_tokens or self.config.max_tokens,
                stream=True,
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error("openai_stream_failed", error=str(e))
            yield f"⚠️ OpenAI streaming error: {e}"
    
    def build_system_prompt(self, request: ChatRequest) -> str:
        """Build system prompt for OpenAI."""
        return request.system_prompt or self.config.system_prompt or DEFAULT_SYSTEM_PROMPT


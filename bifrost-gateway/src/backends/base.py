"""
Base Backend — Abstract interface for AI system integrations.

All AI backends must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from pydantic import BaseModel


@dataclass
class BackendCapabilities:
    """Describes what features a backend supports."""
    
    # Chat features
    supports_streaming: bool = True
    supports_threads: bool = True
    supports_tools: bool = True
    supports_vision: bool = False
    supports_files: bool = False
    
    # Context features
    supports_system_prompt: bool = True
    supports_message_history: bool = True
    max_context_tokens: int = 128000
    
    # Response features
    supports_structured_output: bool = False
    supports_function_calling: bool = True


@dataclass
class BackendConfig:
    """Configuration for a backend instance."""
    
    name: str
    enabled: bool = False
    
    # Connection
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    
    # Model settings
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096
    
    # System prompt
    system_prompt: Optional[str] = None
    
    # Extra backend-specific config
    extra: dict[str, Any] = field(default_factory=dict)


class ChatRequest(BaseModel):
    """Request to send to an AI backend."""
    
    # Message content
    message: str
    
    # Conversation context
    thread_id: Optional[str] = None
    message_history: Optional[list[dict]] = None
    
    # Request metadata
    user_id: Optional[str] = None
    channel_id: Optional[str] = None
    adapter_name: Optional[str] = None
    
    # Optional overrides
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class ChatResponse(BaseModel):
    """Response from an AI backend."""
    
    # Content
    content: str
    
    # Thread tracking
    thread_id: str
    
    # Metadata
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    
    # For Norns-style responses
    current_norn: str = "verdandi"
    
    # Tool calls (if any)
    tool_calls: Optional[list[dict]] = None
    
    # Raw response for debugging
    raw_response: Optional[dict] = None


class BaseBackend(ABC):
    """
    Abstract base class for AI backend integrations.
    
    Implement this class to add support for a new AI system.
    
    Lifecycle:
    1. __init__(config) - Create backend with configuration
    2. initialize() - Async setup (connections, validation)
    3. chat() / stream() - Process messages
    4. shutdown() - Cleanup
    
    Example:
        class MyBackend(BaseBackend):
            @property
            def name(self) -> str:
                return "my_ai"
            
            @property
            def capabilities(self) -> BackendCapabilities:
                return BackendCapabilities(supports_streaming=True)
            
            async def initialize(self) -> None:
                # Setup client
                pass
            
            async def chat(self, request: ChatRequest) -> ChatResponse:
                # Send to AI and get response
                return ChatResponse(content="Hello!", thread_id="123")
    """
    
    def __init__(self, config: BackendConfig):
        """Initialize the backend with configuration."""
        self.config = config
        self._initialized = False
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this backend (e.g., 'norns', 'claude', 'openai')."""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> BackendCapabilities:
        """Return the capabilities of this backend."""
        pass
    
    @property
    def is_enabled(self) -> bool:
        """Check if this backend is enabled."""
        return self.config.enabled
    
    @property
    def is_initialized(self) -> bool:
        """Check if this backend has been initialized."""
        return self._initialized
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the backend (async setup).
        
        Called once when Bifrost starts. Use this for:
        - Establishing connections
        - Validating credentials
        - Loading models
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """
        Shutdown the backend gracefully.
        
        Called when Bifrost stops. Use this for:
        - Closing connections
        - Flushing caches
        - Cleanup
        """
        pass
    
    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Send a message and get a complete response.
        
        Args:
            request: The chat request with message and context
            
        Returns:
            ChatResponse with the AI's response
        """
        pass
    
    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """
        Stream a response token by token.
        
        Override this for backends that support streaming.
        Default implementation calls chat() and yields the full response.
        
        Args:
            request: The chat request with message and context
            
        Yields:
            Response tokens as they arrive
        """
        response = await self.chat(request)
        yield response.content
    
    async def get_wisdom(self) -> str:
        """
        Get a piece of wisdom or greeting.
        
        Override for backends that have special wisdom/greeting modes.
        Default returns a generic greeting.
        """
        return "The bridge stands ready to convey your words."
    
    def build_system_prompt(self, request: ChatRequest) -> str:
        """
        Build the system prompt for a request.
        
        Override to customize system prompt construction.
        """
        return request.system_prompt or self.config.system_prompt or ""
    
    def detect_response_persona(self, content: str) -> str:
        """
        Detect the persona/character in the response.
        
        Override for backends with multiple personas.
        Default returns 'assistant'.
        """
        return "assistant"


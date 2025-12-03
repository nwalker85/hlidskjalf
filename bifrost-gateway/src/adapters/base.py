"""
Base Adapter — Abstract interface for messaging platform integrations.

All messaging platform adapters must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, AsyncIterator

from pydantic import BaseModel


class MessageType(str, Enum):
    """Types of messages that can be sent/received."""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    COMMAND = "command"
    CALLBACK = "callback"  # Button clicks, etc.


@dataclass
class AdapterCapabilities:
    """Describes what features an adapter supports."""
    
    # Message features
    supports_markdown: bool = True
    supports_html: bool = False
    supports_images: bool = False
    supports_files: bool = False
    supports_buttons: bool = False
    supports_threads: bool = True
    
    # Interaction features
    supports_typing_indicator: bool = True
    supports_reactions: bool = False
    supports_edits: bool = False
    supports_deletions: bool = False
    
    # Delivery features
    supports_webhooks: bool = True
    supports_polling: bool = True
    supports_streaming: bool = False
    
    # Limits
    max_message_length: int = 4096
    max_buttons_per_message: int = 10


@dataclass
class AdapterConfig:
    """Configuration for an adapter instance."""
    
    name: str
    enabled: bool = False
    
    # Authentication
    api_token: Optional[str] = None
    webhook_secret: Optional[str] = None
    
    # Access control
    allowed_users: set[str] = field(default_factory=set)
    allowed_channels: set[str] = field(default_factory=set)
    
    # Rate limiting
    rate_limit_messages: int = 30
    rate_limit_window: int = 60
    
    # Extra adapter-specific config
    extra: dict[str, Any] = field(default_factory=dict)


class AdapterMessage(BaseModel):
    """
    Unified message format for all adapters.
    
    Adapters translate platform-specific messages to/from this format.
    """
    
    # Identity
    adapter_name: str
    message_id: str
    
    # Sender info
    user_id: str
    user_name: Optional[str] = None
    user_display_name: Optional[str] = None
    
    # Channel/conversation info
    channel_id: str
    channel_name: Optional[str] = None
    thread_id: Optional[str] = None
    
    # Content
    message_type: MessageType = MessageType.TEXT
    content: str
    
    # Metadata
    timestamp: datetime = None
    is_bot: bool = False
    raw_payload: Optional[dict] = None
    
    class Config:
        use_enum_values = True
    
    def __init__(self, **data):
        if data.get('timestamp') is None:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)


class AdapterResponse(BaseModel):
    """
    Response to send back through an adapter.
    """
    
    # Content
    content: str
    
    # Formatting
    parse_mode: Optional[str] = "markdown"  # markdown, html, plain
    
    # Optional features
    buttons: Optional[list[dict]] = None
    image_url: Optional[str] = None
    file_url: Optional[str] = None
    
    # Reply context
    reply_to_message_id: Optional[str] = None
    thread_id: Optional[str] = None
    
    # Metadata from Norns
    current_norn: str = "verdandi"
    norns_thread_id: Optional[str] = None


class BaseAdapter(ABC):
    """
    Abstract base class for messaging platform adapters.
    
    Implement this class to add support for a new messaging platform.
    
    Lifecycle:
    1. __init__(config) - Create adapter with configuration
    2. initialize() - Async setup (connections, etc.)
    3. handle_webhook() / start_polling() - Process messages
    4. shutdown() - Cleanup
    
    Example:
        class MyAdapter(BaseAdapter):
            @property
            def name(self) -> str:
                return "my_platform"
            
            @property
            def capabilities(self) -> AdapterCapabilities:
                return AdapterCapabilities(supports_markdown=True)
            
            async def initialize(self) -> None:
                # Setup connections
                pass
            
            async def handle_webhook(self, payload: dict) -> bool:
                message = self.parse_message(payload)
                response = await self.message_handler(message)
                await self.send_response(message, response)
                return True
            
            async def send_response(self, original: AdapterMessage, response: AdapterResponse) -> bool:
                # Send to platform
                return True
    """
    
    def __init__(self, config: AdapterConfig):
        """Initialize the adapter with configuration."""
        self.config = config
        self._message_handler: Optional[Callable[[AdapterMessage], AdapterResponse]] = None
        self._initialized = False
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this adapter (e.g., 'telegram', 'slack')."""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """Return the capabilities of this adapter."""
        pass
    
    @property
    def is_enabled(self) -> bool:
        """Check if this adapter is enabled."""
        return self.config.enabled and self.config.api_token is not None
    
    @property
    def is_initialized(self) -> bool:
        """Check if this adapter has been initialized."""
        return self._initialized
    
    def set_message_handler(self, handler: Callable[[AdapterMessage], AdapterResponse]) -> None:
        """
        Set the handler function for incoming messages.
        
        The handler receives an AdapterMessage and should return an AdapterResponse.
        This is typically set by the Bifrost core to route messages to the Norns.
        """
        self._message_handler = handler
    
    async def message_handler(self, message: AdapterMessage) -> AdapterResponse:
        """
        Process an incoming message through the registered handler.
        
        Override this to add pre/post processing, logging, etc.
        """
        if self._message_handler is None:
            return AdapterResponse(
                content="⚠️ No message handler configured. Bifrost is not fully initialized.",
                current_norn="verdandi",
            )
        return await self._message_handler(message)
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the adapter (async setup).
        
        Called once when Bifrost starts. Use this for:
        - Establishing connections
        - Validating credentials
        - Setting up webhook handlers
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """
        Shutdown the adapter gracefully.
        
        Called when Bifrost stops. Use this for:
        - Closing connections
        - Flushing buffers
        - Cleanup
        """
        pass
    
    @abstractmethod
    async def handle_webhook(self, payload: dict) -> bool:
        """
        Handle an incoming webhook payload from the platform.
        
        Args:
            payload: The raw webhook payload (already parsed from JSON)
            
        Returns:
            True if the webhook was processed successfully
        """
        pass
    
    @abstractmethod
    async def send_response(
        self,
        original_message: AdapterMessage,
        response: AdapterResponse,
    ) -> bool:
        """
        Send a response back to the platform.
        
        Args:
            original_message: The message we're responding to
            response: The response to send
            
        Returns:
            True if the message was sent successfully
        """
        pass
    
    def verify_webhook(self, secret: str, payload: bytes, signature: str = "") -> bool:
        """
        Verify that a webhook request is authentic.
        
        Override this with platform-specific signature verification.
        
        Args:
            secret: The expected secret/token
            payload: The raw request body
            signature: The signature header (if applicable)
            
        Returns:
            True if the webhook is authentic
        """
        if not self.config.webhook_secret:
            return True
        return secret == self.config.webhook_secret
    
    def is_user_allowed(self, user_id: str) -> bool:
        """
        Check if a user is allowed to use this adapter.
        
        Args:
            user_id: The platform-specific user ID
            
        Returns:
            True if the user is allowed (or if no whitelist is configured)
        """
        if not self.config.allowed_users:
            return True
        return user_id in self.config.allowed_users
    
    def is_channel_allowed(self, channel_id: str) -> bool:
        """
        Check if a channel is allowed for this adapter.
        
        Args:
            channel_id: The platform-specific channel ID
            
        Returns:
            True if the channel is allowed (or if no whitelist is configured)
        """
        if not self.config.allowed_channels:
            return True
        return channel_id in self.config.allowed_channels
    
    def truncate_message(self, content: str) -> list[str]:
        """
        Split a message into chunks that fit the platform's limits.
        
        Args:
            content: The full message content
            
        Returns:
            List of message chunks
        """
        max_len = self.capabilities.max_message_length
        if len(content) <= max_len:
            return [content]
        
        # Split at max length, trying to break at whitespace
        chunks = []
        while content:
            if len(content) <= max_len:
                chunks.append(content)
                break
            
            # Find a good break point
            break_point = content.rfind(' ', 0, max_len)
            if break_point == -1:
                break_point = max_len
            
            chunks.append(content[:break_point])
            content = content[break_point:].lstrip()
        
        return chunks
    
    def format_norn_indicator(self, norn: str) -> str:
        """Get the emoji indicator for a Norn."""
        indicators = {
            "urd": "🕰️",
            "verdandi": "⏱️",
            "skuld": "🔮",
        }
        return indicators.get(norn.lower(), "⏱️")


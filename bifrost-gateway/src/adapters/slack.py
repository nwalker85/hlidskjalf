"""
Slack Adapter — Integration with Slack Bot API.

This adapter implements the BaseAdapter interface for Slack,
handling Events API webhooks, message formatting, and conversation threads.

Status: SKELETON - Not yet implemented
"""

from typing import Optional

import structlog

from src.adapters.base import (
    BaseAdapter,
    AdapterCapabilities,
    AdapterConfig,
    AdapterMessage,
    AdapterResponse,
    MessageType,
)
from src.adapters.registry import register_adapter

logger = structlog.get_logger(__name__)


@register_adapter("slack")
class SlackAdapter(BaseAdapter):
    """
    Slack messaging adapter.
    
    Supports:
    - Events API webhooks
    - Markdown (mrkdwn) formatting
    - Threading
    - User/Channel whitelisting
    
    TODO:
    - [ ] Implement OAuth flow
    - [ ] Add slash command support
    - [ ] Add interactive components (buttons, modals)
    - [ ] Add file upload support
    """
    
    @property
    def name(self) -> str:
        return "slack"
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_markdown=True,  # Slack uses mrkdwn
            supports_html=False,
            supports_images=True,
            supports_files=True,
            supports_buttons=True,
            supports_threads=True,
            supports_typing_indicator=False,  # Slack doesn't have this
            supports_reactions=True,
            supports_edits=True,
            supports_deletions=True,
            supports_webhooks=True,
            supports_polling=False,
            supports_streaming=False,
            max_message_length=4000,  # Slack's limit
            max_buttons_per_message=25,
        )
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self._client = None
        self._bot_user_id: Optional[str] = None
    
    async def initialize(self) -> None:
        """Initialize the Slack adapter."""
        if not self.config.api_token:
            logger.warning("slack_no_token", hint="Set SLACK_BOT_TOKEN")
            return
        
        # TODO: Initialize Slack client
        # from slack_sdk.web.async_client import AsyncWebClient
        # self._client = AsyncWebClient(token=self.config.api_token)
        # 
        # # Get bot user ID for filtering
        # auth_response = await self._client.auth_test()
        # self._bot_user_id = auth_response["user_id"]
        
        self._initialized = True
        logger.info("slack_adapter_initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the Slack adapter."""
        self._client = None
        self._initialized = False
        logger.info("slack_adapter_shutdown")
    
    def verify_webhook(self, secret: str, payload: bytes, signature: str = "") -> bool:
        """
        Verify Slack webhook signature.
        
        Slack uses HMAC-SHA256 with the signing secret.
        Headers: X-Slack-Signature, X-Slack-Request-Timestamp
        """
        if not self.config.webhook_secret:
            return True
        
        # TODO: Implement Slack signature verification
        # import hmac
        # import hashlib
        # import time
        # 
        # timestamp = request.headers.get("X-Slack-Request-Timestamp")
        # sig_basestring = f"v0:{timestamp}:{payload.decode()}"
        # expected = "v0=" + hmac.new(
        #     self.config.webhook_secret.encode(),
        #     sig_basestring.encode(),
        #     hashlib.sha256
        # ).hexdigest()
        # 
        # return hmac.compare_digest(signature, expected)
        
        return True
    
    async def handle_webhook(self, payload: dict) -> bool:
        """
        Handle incoming Slack Events API webhook.
        
        Event types:
        - url_verification: Challenge response
        - event_callback: Actual events (message, app_mention, etc.)
        """
        event_type = payload.get("type")
        
        # URL verification challenge
        if event_type == "url_verification":
            # This should be handled at the route level
            return True
        
        # Event callback
        if event_type == "event_callback":
            event = payload.get("event", {})
            return await self._handle_event(event)
        
        logger.warning("slack_unknown_event_type", type=event_type)
        return True
    
    async def _handle_event(self, event: dict) -> bool:
        """Handle a Slack event."""
        event_type = event.get("type")
        
        # Skip bot messages to avoid loops
        if event.get("bot_id") or event.get("user") == self._bot_user_id:
            return True
        
        if event_type == "message":
            return await self._handle_message(event)
        elif event_type == "app_mention":
            return await self._handle_mention(event)
        
        logger.debug("slack_unhandled_event", type=event_type)
        return True
    
    async def _handle_message(self, event: dict) -> bool:
        """Handle a message event."""
        # Skip messages in channels unless mentioned
        channel_type = event.get("channel_type")
        if channel_type == "channel" and self._bot_user_id not in event.get("text", ""):
            return True
        
        # Check authorization
        user_id = event.get("user", "")
        channel_id = event.get("channel", "")
        
        if not self.is_user_allowed(user_id):
            logger.warning("slack_unauthorized_user", user_id=user_id)
            return True
        
        if not self.is_channel_allowed(channel_id):
            logger.warning("slack_unauthorized_channel", channel_id=channel_id)
            return True
        
        # Create unified message
        message = AdapterMessage(
            adapter_name=self.name,
            message_id=event.get("ts", ""),
            user_id=user_id,
            channel_id=channel_id,
            thread_id=event.get("thread_ts"),
            message_type=MessageType.TEXT,
            content=self._clean_message_text(event.get("text", "")),
            raw_payload=event,
        )
        
        # Process through handler
        response = await self.message_handler(message)
        
        # Send response
        await self.send_response(message, response)
        
        return True
    
    async def _handle_mention(self, event: dict) -> bool:
        """Handle an app_mention event."""
        # Same as message but always respond
        return await self._handle_message(event)
    
    def _clean_message_text(self, text: str) -> str:
        """Remove bot mention from message text."""
        if self._bot_user_id:
            text = text.replace(f"<@{self._bot_user_id}>", "").strip()
        return text
    
    async def send_response(
        self,
        original_message: AdapterMessage,
        response: AdapterResponse,
    ) -> bool:
        """Send response to Slack."""
        if not self._client:
            logger.error("slack_client_not_initialized")
            return False
        
        try:
            # Format with Norn indicator
            norn_emoji = self.format_norn_indicator(response.current_norn)
            content = f"{norn_emoji} {response.content}"
            
            # Convert markdown to Slack mrkdwn
            content = self._convert_to_mrkdwn(content)
            
            # Handle long messages
            chunks = self.truncate_message(content)
            
            for chunk in chunks:
                # TODO: Actually send via Slack API
                # await self._client.chat_postMessage(
                #     channel=original_message.channel_id,
                #     text=chunk,
                #     thread_ts=original_message.thread_id or original_message.message_id,
                # )
                pass
            
            return True
        except Exception as e:
            logger.error("slack_send_failed", error=str(e))
            return False
    
    def _convert_to_mrkdwn(self, markdown: str) -> str:
        """
        Convert standard markdown to Slack mrkdwn.
        
        Differences:
        - Bold: **text** -> *text*
        - Italic: *text* -> _text_
        - Code: `code` -> `code` (same)
        - Links: [text](url) -> <url|text>
        """
        # TODO: Implement markdown conversion
        return markdown


# =============================================================================
# Helper for URL verification (used at route level)
# =============================================================================

def handle_url_verification(payload: dict) -> dict:
    """
    Handle Slack URL verification challenge.
    
    Call this at the route level before the adapter:
    
        if payload.get("type") == "url_verification":
            return handle_url_verification(payload)
    """
    return {"challenge": payload.get("challenge")}


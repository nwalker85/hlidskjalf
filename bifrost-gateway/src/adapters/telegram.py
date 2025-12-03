"""
Telegram Adapter — Integration with Telegram Bot API.

This adapter implements the BaseAdapter interface for Telegram,
handling webhooks, message formatting, and conversation state.
"""

import time
from typing import Optional

import redis.asyncio as redis
import structlog
from telegram import Bot, Update
from telegram.constants import ParseMode, ChatAction
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters

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


@register_adapter("telegram")
class TelegramAdapter(BaseAdapter):
    """
    Telegram messaging adapter.
    
    Supports:
    - Webhook-based message receiving
    - Markdown formatting
    - Typing indicators
    - Conversation threads via Redis
    - User whitelisting
    - Rate limiting
    """
    
    @property
    def name(self) -> str:
        return "telegram"
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_markdown=True,
            supports_html=True,
            supports_images=True,
            supports_files=True,
            supports_buttons=True,
            supports_threads=True,
            supports_typing_indicator=True,
            supports_reactions=False,
            supports_edits=True,
            supports_deletions=True,
            supports_webhooks=True,
            supports_polling=True,
            supports_streaming=False,
            max_message_length=4096,
            max_buttons_per_message=100,
        )
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self._app: Optional[Application] = None
        self._bot: Optional[Bot] = None
        self._redis: Optional[redis.Redis] = None
    
    async def initialize(self) -> None:
        """Initialize Telegram bot and Redis connection."""
        if not self.config.api_token:
            logger.warning("telegram_no_token", hint="Set TELEGRAM_BOT_TOKEN")
            return
        
        # Build Telegram application
        self._app = (
            Application.builder()
            .token(self.config.api_token)
            .build()
        )
        self._bot = self._app.bot
        
        # Register command handlers
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("help", self._cmd_help))
        self._app.add_handler(CommandHandler("wisdom", self._cmd_wisdom))
        self._app.add_handler(CommandHandler("reset", self._cmd_reset))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text_message)
        )
        
        # Initialize Redis for thread storage
        redis_url = self.config.extra.get("redis_url", "redis://localhost:6379/3")
        try:
            self._redis = redis.from_url(redis_url)
            await self._redis.ping()
            logger.info("telegram_redis_connected", url=redis_url)
        except Exception as e:
            logger.warning("telegram_redis_failed", error=str(e))
            self._redis = None
        
        # Initialize the application
        await self._app.initialize()
        self._initialized = True
        logger.info("telegram_adapter_initialized")
    
    async def shutdown(self) -> None:
        """Shutdown Telegram application and Redis."""
        if self._app:
            await self._app.shutdown()
        if self._redis:
            await self._redis.close()
        self._initialized = False
        logger.info("telegram_adapter_shutdown")
    
    async def handle_webhook(self, payload: dict) -> bool:
        """Process an incoming Telegram webhook."""
        if not self._app:
            logger.error("telegram_not_initialized")
            return False
        
        try:
            update = Update.de_json(payload, self._app.bot)
            await self._app.process_update(update)
            return True
        except Exception as e:
            logger.error("telegram_webhook_error", error=str(e))
            return False
    
    async def send_response(
        self,
        original_message: AdapterMessage,
        response: AdapterResponse,
    ) -> bool:
        """Send a response to Telegram."""
        if not self._bot:
            return False
        
        try:
            # Format with Norn indicator
            norn_emoji = self.format_norn_indicator(response.current_norn)
            content = f"{norn_emoji} {response.content}"
            
            # Handle long messages
            chunks = self.truncate_message(content)
            
            parse_mode = (
                ParseMode.MARKDOWN 
                if response.parse_mode == "markdown" 
                else ParseMode.HTML if response.parse_mode == "html" 
                else None
            )
            
            for chunk in chunks:
                await self._bot.send_message(
                    chat_id=original_message.channel_id,
                    text=chunk,
                    parse_mode=parse_mode,
                    reply_to_message_id=response.reply_to_message_id,
                )
            
            return True
        except Exception as e:
            logger.error("telegram_send_failed", error=str(e))
            return False
    
    # =========================================================================
    # Redis Thread Storage
    # =========================================================================
    
    async def _get_thread_id(self, chat_id: int) -> Optional[str]:
        """Get conversation thread ID for a chat."""
        if not self._redis:
            return None
        try:
            thread_id = await self._redis.get(f"bifrost:telegram:thread:{chat_id}")
            return thread_id.decode() if thread_id else None
        except Exception:
            return None
    
    async def _set_thread_id(self, chat_id: int, thread_id: str):
        """Store conversation thread ID."""
        if not self._redis:
            return
        try:
            await self._redis.setex(
                f"bifrost:telegram:thread:{chat_id}",
                86400,  # 24 hour expiry
                thread_id,
            )
        except Exception as e:
            logger.warning("redis_set_failed", error=str(e))
    
    async def _clear_thread_id(self, chat_id: int):
        """Clear conversation thread ID."""
        if not self._redis:
            return
        try:
            await self._redis.delete(f"bifrost:telegram:thread:{chat_id}")
        except Exception:
            pass
    
    async def _check_rate_limit(self, user_id: int) -> bool:
        """Check rate limit. Returns True if allowed."""
        if not self._redis:
            return True
        
        key = f"bifrost:telegram:ratelimit:{user_id}"
        try:
            current = await self._redis.incr(key)
            if current == 1:
                await self._redis.expire(key, self.config.rate_limit_window)
            return current <= self.config.rate_limit_messages
        except Exception:
            return True
    
    # =========================================================================
    # Command Handlers
    # =========================================================================
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        
        if not self.is_user_allowed(str(user.id)):
            await update.message.reply_text(
                "⛔ You are not authorized to consult the Norns.\n"
                "Contact the administrator for access."
            )
            logger.warning("telegram_unauthorized", user_id=user.id)
            return
        
        welcome = (
            f"🌳 *Hail, {user.first_name}!*\n\n"
            "You have crossed *Bifrost*, the rainbow bridge, "
            "and now stand before the *Well of Urðr* beneath *Yggdrasil*.\n\n"
            "The three sisters await your questions:\n"
            "🕰️ *Urðr* — studies the past\n"
            "⏱️ *Verðandi* — surveys the present\n"
            "🔮 *Skuld* — shapes the future\n\n"
            "Simply speak, and they shall weave a response.\n\n"
            "_Commands:_\n"
            "/wisdom — Receive wisdom from the Norns\n"
            "/reset — Start a new conversation\n"
            "/status — Check connection to the realms\n"
            "/help — Show this message"
        )
        await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)
        logger.info("telegram_user_started", user_id=user.id)
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        await self._cmd_start(update, context)
    
    async def _cmd_wisdom(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /wisdom command."""
        user = update.effective_user
        if not self.is_user_allowed(str(user.id)):
            return
        
        await update.message.chat.send_action(ChatAction.TYPING)
        
        # Create a special wisdom request message
        message = AdapterMessage(
            adapter_name=self.name,
            message_id=str(update.message.message_id),
            user_id=str(user.id),
            user_name=user.username,
            user_display_name=user.first_name,
            channel_id=str(update.effective_chat.id),
            message_type=MessageType.COMMAND,
            content="/wisdom",
        )
        
        response = await self.message_handler(message)
        await self.send_response(message, response)
    
    async def _cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reset command."""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        if not self.is_user_allowed(str(user.id)):
            return
        
        await self._clear_thread_id(chat_id)
        await update.message.reply_text(
            "🌊 The waters of *Urðr's Well* have been stirred.\n"
            "Your thread with the Norns begins anew.",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info("telegram_conversation_reset", user_id=user.id, chat_id=chat_id)
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        user = update.effective_user
        if not self.is_user_allowed(str(user.id)):
            return
        
        redis_status = "✅ Connected" if self._redis else "⚠️ Not configured"
        if self._redis:
            try:
                await self._redis.ping()
            except Exception:
                redis_status = "❌ Unreachable"
        
        thread_id = await self._get_thread_id(update.effective_chat.id) or "None"
        thread_display = f"`{thread_id[:20]}...`" if len(thread_id) > 20 else f"`{thread_id}`"
        
        status = (
            "🌉 *Bifrost Gateway Status*\n\n"
            f"*Adapter:* Telegram ✅\n"
            f"*Redis:* {redis_status}\n"
            f"*Thread ID:* {thread_display}"
        )
        await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)
    
    # =========================================================================
    # Message Handler
    # =========================================================================
    
    async def _handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages."""
        user = update.effective_user
        chat_id = update.effective_chat.id
        message_text = update.message.text
        
        # Authorization check
        if not self.is_user_allowed(str(user.id)):
            logger.warning("telegram_unauthorized_message", user_id=user.id)
            return
        
        # Rate limit check
        if not await self._check_rate_limit(user.id):
            await update.message.reply_text(
                "⏳ The Norns need rest. Please wait a moment before asking again."
            )
            return
        
        logger.info(
            "telegram_message_received",
            user_id=user.id,
            username=user.username,
            chat_id=chat_id,
            length=len(message_text),
        )
        
        # Show typing indicator
        await update.message.chat.send_action(ChatAction.TYPING)
        
        # Get existing thread
        thread_id = await self._get_thread_id(chat_id)
        
        # Create unified message
        message = AdapterMessage(
            adapter_name=self.name,
            message_id=str(update.message.message_id),
            user_id=str(user.id),
            user_name=user.username,
            user_display_name=user.first_name,
            channel_id=str(chat_id),
            thread_id=thread_id,
            message_type=MessageType.TEXT,
            content=message_text,
            raw_payload=update.to_dict(),
        )
        
        # Process through handler
        start_time = time.time()
        response = await self.message_handler(message)
        elapsed = time.time() - start_time
        
        # Store thread ID
        if response.norns_thread_id:
            await self._set_thread_id(chat_id, response.norns_thread_id)
        
        # Send response
        await self.send_response(message, response)
        
        logger.info(
            "telegram_message_processed",
            user_id=user.id,
            norn=response.current_norn,
            response_length=len(response.content),
            elapsed=round(elapsed, 2),
        )
    
    # =========================================================================
    # Webhook Management
    # =========================================================================
    
    async def set_webhook(self, url: str) -> bool:
        """Set the Telegram webhook URL."""
        if not self._bot:
            return False
        
        try:
            success = await self._bot.set_webhook(
                url=url,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True,
            )
            if success:
                logger.info("telegram_webhook_set", url=url)
            return success
        except Exception as e:
            logger.error("telegram_webhook_set_failed", error=str(e))
            return False
    
    async def delete_webhook(self) -> bool:
        """Remove the Telegram webhook."""
        if not self._bot:
            return False
        
        try:
            success = await self._bot.delete_webhook(drop_pending_updates=True)
            if success:
                logger.info("telegram_webhook_deleted")
            return success
        except Exception as e:
            logger.error("telegram_webhook_delete_failed", error=str(e))
            return False
    
    async def get_webhook_info(self) -> dict:
        """Get current webhook information."""
        if not self._bot:
            return {}
        
        try:
            info = await self._bot.get_webhook_info()
            return {
                "url": info.url,
                "pending_update_count": info.pending_update_count,
                "max_connections": info.max_connections,
                "ip_address": info.ip_address,
                "last_error_date": info.last_error_date,
                "last_error_message": info.last_error_message,
            }
        except Exception as e:
            logger.error("telegram_webhook_info_failed", error=str(e))
            return {"error": str(e)}


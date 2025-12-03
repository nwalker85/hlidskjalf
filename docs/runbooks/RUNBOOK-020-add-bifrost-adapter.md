# RUNBOOK-020: Add a New Bifrost Adapter

## Overview

This runbook describes how to add a new messaging platform adapter to Bifrost Gateway.
Bifrost uses an extensible adapter pattern that allows new integrations to be added
with minimal changes to the core system.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BIFROST GATEWAY                               │
│                                                                     │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │
│  │  Telegram   │   │    Slack    │   │   Discord   │   ...        │
│  │   Adapter   │   │   Adapter   │   │   Adapter   │              │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘              │
│         │                 │                 │                      │
│         └────────────────┼─────────────────┘                      │
│                          ▼                                         │
│              ┌───────────────────────┐                            │
│              │    Adapter Registry    │                            │
│              │   (auto-discovery)     │                            │
│              └───────────┬───────────┘                            │
│                          │                                         │
│                          ▼                                         │
│              ┌───────────────────────┐                            │
│              │   Message Handler     │                            │
│              │  (routes to Norns)    │                            │
│              └───────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Python 3.11+
- Understanding of the target platform's API
- API credentials for the target platform

## Steps

### 1. Create the Adapter File

Create a new file in `bifrost-gateway/src/adapters/`:

```bash
touch bifrost-gateway/src/adapters/myplatform.py
```

### 2. Implement the Adapter Class

Use this template:

```python
"""
MyPlatform Adapter — Integration with MyPlatform API.
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


@register_adapter("myplatform")  # This name must be unique
class MyPlatformAdapter(BaseAdapter):
    """
    MyPlatform messaging adapter.
    
    Document what this adapter supports and any platform-specific behavior.
    """
    
    @property
    def name(self) -> str:
        return "myplatform"
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_markdown=True,
            supports_html=False,
            supports_images=True,
            supports_files=False,
            supports_buttons=True,
            supports_threads=True,
            supports_typing_indicator=True,
            supports_reactions=False,
            supports_edits=False,
            supports_deletions=False,
            supports_webhooks=True,
            supports_polling=False,
            supports_streaming=False,
            max_message_length=2000,  # Platform's limit
            max_buttons_per_message=5,
        )
    
    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self._client = None  # Platform-specific client
    
    async def initialize(self) -> None:
        """Initialize the adapter."""
        if not self.config.api_token:
            logger.warning("myplatform_no_token")
            return
        
        # Initialize platform client
        # self._client = MyPlatformClient(self.config.api_token)
        
        self._initialized = True
        logger.info("myplatform_adapter_initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the adapter."""
        # Close connections, cleanup
        self._initialized = False
        logger.info("myplatform_adapter_shutdown")
    
    async def handle_webhook(self, payload: dict) -> bool:
        """
        Handle incoming webhook from the platform.
        
        1. Parse the platform-specific payload
        2. Convert to AdapterMessage
        3. Call self.message_handler(message)
        4. Send response back to platform
        """
        try:
            # Parse platform payload into unified message
            message = self._parse_webhook(payload)
            
            # Check authorization
            if not self.is_user_allowed(message.user_id):
                logger.warning("myplatform_unauthorized", user_id=message.user_id)
                return True  # Acknowledge but don't process
            
            # Process through handler
            response = await self.message_handler(message)
            
            # Send response
            await self.send_response(message, response)
            
            return True
        except Exception as e:
            logger.error("myplatform_webhook_error", error=str(e))
            return False
    
    async def send_response(
        self,
        original_message: AdapterMessage,
        response: AdapterResponse,
    ) -> bool:
        """Send response back to the platform."""
        try:
            # Format message for platform
            norn_emoji = self.format_norn_indicator(response.current_norn)
            content = f"{norn_emoji} {response.content}"
            
            # Handle message length limits
            chunks = self.truncate_message(content)
            
            for chunk in chunks:
                # Send via platform API
                # await self._client.send_message(
                #     channel_id=original_message.channel_id,
                #     text=chunk,
                # )
                pass
            
            return True
        except Exception as e:
            logger.error("myplatform_send_failed", error=str(e))
            return False
    
    def _parse_webhook(self, payload: dict) -> AdapterMessage:
        """Convert platform webhook to unified message."""
        # Extract fields from platform-specific payload
        return AdapterMessage(
            adapter_name=self.name,
            message_id=payload.get("message_id", "unknown"),
            user_id=payload.get("user", {}).get("id", "unknown"),
            user_name=payload.get("user", {}).get("username"),
            user_display_name=payload.get("user", {}).get("display_name"),
            channel_id=payload.get("channel_id", "unknown"),
            message_type=MessageType.TEXT,
            content=payload.get("text", ""),
            raw_payload=payload,
        )
```

### 3. Register the Adapter for Auto-Import

Edit `bifrost-gateway/src/adapters/registry.py` and add the import:

```python
def _auto_register_adapters():
    """Import all adapter modules to trigger registration."""
    # ... existing imports ...
    
    try:
        from src.adapters import myplatform  # noqa: F401
        logger.debug("loaded_adapter_module", module="myplatform")
    except ImportError as e:
        logger.warning("adapter_import_failed", module="myplatform", error=str(e))
```

### 4. Add Configuration

Edit `bifrost-gateway/src/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # =========================================================================
    # MYPLATFORM ADAPTER
    # =========================================================================
    MYPLATFORM_ENABLED: bool = False
    MYPLATFORM_API_TOKEN: Optional[str] = None
    MYPLATFORM_WEBHOOK_SECRET: Optional[str] = None
    MYPLATFORM_ALLOWED_USERS: str = ""
    
    def get_myplatform_config(self) -> AdapterConfig:
        """Get MyPlatform adapter configuration."""
        return AdapterConfig(
            name="myplatform",
            enabled=self.MYPLATFORM_ENABLED and bool(self.MYPLATFORM_API_TOKEN),
            api_token=self.MYPLATFORM_API_TOKEN,
            webhook_secret=self.MYPLATFORM_WEBHOOK_SECRET,
            allowed_users=self._parse_csv(self.MYPLATFORM_ALLOWED_USERS),
            extra={"redis_url": self.REDIS_URL},
        )
    
    def get_all_adapter_configs(self) -> dict[str, AdapterConfig]:
        """Get all adapter configurations."""
        return {
            # ... existing adapters ...
            "myplatform": self.get_myplatform_config(),
        }
```

### 5. Add Webhook Route (if needed)

If your platform needs special webhook handling, add a route in `bifrost-gateway/src/main.py`:

```python
@app.post("/webhook/myplatform")
async def myplatform_webhook(request: Request):
    """MyPlatform webhook endpoint."""
    adapter = get_adapter("myplatform")
    if not adapter or not adapter.is_enabled:
        raise HTTPException(status_code=503, detail="MyPlatform adapter not enabled")
    
    payload = await request.json()
    
    # Handle any platform-specific verification
    # ...
    
    success = await adapter.handle_webhook(payload)
    return {"ok": success}
```

### 6. Add Dependencies

If your adapter needs additional Python packages, add them to `pyproject.toml`:

```toml
dependencies = [
    # ... existing deps ...
    "myplatform-sdk>=1.0.0",
]
```

### 7. Update Docker Compose

Add environment variables for the new adapter:

```yaml
environment:
  - MYPLATFORM_ENABLED=${MYPLATFORM_ENABLED:-false}
  - MYPLATFORM_API_TOKEN=${MYPLATFORM_API_TOKEN:-}
  - MYPLATFORM_WEBHOOK_SECRET=${MYPLATFORM_WEBHOOK_SECRET:-}
  - MYPLATFORM_ALLOWED_USERS=${MYPLATFORM_ALLOWED_USERS:-}
```

### 8. Test the Adapter

```bash
# Build and run
cd bifrost-gateway
docker-compose build
docker-compose up -d

# Check adapter status
curl http://localhost:8050/adapters

# Should show your adapter in the list:
# {"adapters": [..., {"name": "myplatform", "enabled": true, "initialized": true}]}
```

## Adapter Interface Reference

### Required Methods

| Method | Description |
|--------|-------------|
| `name` | Property returning unique adapter name |
| `capabilities` | Property returning `AdapterCapabilities` |
| `initialize()` | Async setup (connections, validation) |
| `shutdown()` | Async cleanup |
| `handle_webhook(payload)` | Process incoming webhook |
| `send_response(message, response)` | Send response to platform |

### Optional Overrides

| Method | Description |
|--------|-------------|
| `verify_webhook(secret, payload, signature)` | Custom webhook verification |
| `is_user_allowed(user_id)` | Custom authorization logic |
| `truncate_message(content)` | Custom message splitting |
| `message_handler(message)` | Pre/post processing |

### AdapterMessage Fields

| Field | Type | Description |
|-------|------|-------------|
| `adapter_name` | str | Name of the source adapter |
| `message_id` | str | Platform-specific message ID |
| `user_id` | str | Platform-specific user ID |
| `user_name` | str | Username |
| `user_display_name` | str | Display name |
| `channel_id` | str | Platform-specific channel/chat ID |
| `thread_id` | str | Conversation thread ID |
| `message_type` | MessageType | TEXT, COMMAND, IMAGE, etc. |
| `content` | str | Message content |
| `raw_payload` | dict | Original webhook payload |

### AdapterResponse Fields

| Field | Type | Description |
|-------|------|-------------|
| `content` | str | Response text |
| `parse_mode` | str | markdown, html, plain |
| `buttons` | list | Optional button definitions |
| `current_norn` | str | Which Norn is responding |
| `norns_thread_id` | str | Thread ID from Norns |

## Checklist

- [ ] Created adapter file in `src/adapters/`
- [ ] Implemented all required methods
- [ ] Used `@register_adapter("name")` decorator
- [ ] Added auto-import in `registry.py`
- [ ] Added configuration in `config.py`
- [ ] Added webhook route in `main.py` (if needed)
- [ ] Added dependencies to `pyproject.toml`
- [ ] Updated `docker-compose.yml`
- [ ] Tested adapter initialization
- [ ] Tested webhook handling
- [ ] Tested response sending
- [ ] Documented platform-specific setup

## Common Patterns

### Rate Limiting with Redis

```python
async def _check_rate_limit(self, user_id: str) -> bool:
    if not self._redis:
        return True
    
    key = f"bifrost:{self.name}:ratelimit:{user_id}"
    current = await self._redis.incr(key)
    if current == 1:
        await self._redis.expire(key, self.config.rate_limit_window)
    return current <= self.config.rate_limit_messages
```

### Thread Persistence

```python
async def _get_thread_id(self, channel_id: str) -> Optional[str]:
    if not self._redis:
        return None
    key = f"bifrost:{self.name}:thread:{channel_id}"
    thread_id = await self._redis.get(key)
    return thread_id.decode() if thread_id else None

async def _set_thread_id(self, channel_id: str, thread_id: str):
    if not self._redis:
        return
    key = f"bifrost:{self.name}:thread:{channel_id}"
    await self._redis.setex(key, 86400, thread_id)  # 24h expiry
```

### Webhook Signature Verification

```python
def verify_webhook(self, secret: str, payload: bytes, signature: str = "") -> bool:
    import hmac
    import hashlib
    
    expected = hmac.new(
        self.config.webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)
```

## Troubleshooting

### Adapter not appearing in `/adapters`

1. Check that the adapter file is imported in `registry.py`
2. Verify `@register_adapter` decorator is present
3. Check logs for import errors

### Adapter shows as not initialized

1. Check that `api_token` is set
2. Check that `ADAPTER_ENABLED=true`
3. Look at logs for initialization errors

### Webhooks not being received

1. Verify the webhook URL is set correctly with the platform
2. Check that the route exists in `main.py`
3. Verify network connectivity (ngrok/tunnel is running)

## Related Runbooks

- [RUNBOOK-001: Deploy Docker Service](./RUNBOOK-001-deploy-docker-service.md)
- [RUNBOOK-002: Add Traefik Domain](./RUNBOOK-002-add-traefik-domain.md)

---

*Last updated: 2024*


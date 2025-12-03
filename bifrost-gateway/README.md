# 🌈 Bifrost Gateway

> *The burning rainbow bridge that connects Midgard to Asgard*

Bifrost Gateway is the external services integration layer for Hliðskjálf. It provides a secure, extensible bridge between external messaging platforms and the internal Norns AI agent system.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERNET                                 │
│                            │                                     │
│                    ┌───────▼───────┐                            │
│                    │   Cloudflare   │                            │
│                    │   Tunnel /     │                            │
│                    │   ngrok        │                            │
│                    └───────┬───────┘                            │
└────────────────────────────┼────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│  BIFROST GATEWAY (:8050)   │                    DMZ             │
│                    ┌───────▼───────┐                            │
│  ┌──────────┐     │   Webhook     │     ┌──────────┐           │
│  │ Telegram │────▶│   Router      │◀────│  Slack   │           │
│  │ Adapter  │     │               │     │ Adapter  │           │
│  └──────────┘     └───────┬───────┘     └──────────┘           │
│                           │                                     │
│                   ┌───────▼───────┐                            │
│                   │   Adapter     │                            │
│                   │   Registry    │                            │
│                   └───────┬───────┘                            │
│                           │                                     │
│                   ┌───────▼───────┐                            │
│                   │   Message     │                            │
│                   │   Handler     │                            │
│                   └───────┬───────┘                            │
└────────────────────────────┼────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────┐
│  INTERNAL NETWORK          │                                     │
│                    ┌───────▼───────┐                            │
│                    │   Norns API   │                            │
│                    │   (:2024)     │                            │
│                    └───────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **🔌 Extensible Adapter Pattern** — Add new platforms easily
- **🔐 User Whitelisting** — Control who can talk to Norns
- **⏱️ Rate Limiting** — Prevent abuse with Redis-backed limits
- **🧵 Conversation Threads** — Persistent context across messages
- **🔒 Webhook Validation** — Platform-specific signature verification

## Supported Platforms (Adapters)

| Platform | Status | Features |
|----------|--------|----------|
| Telegram | ✅ Ready | Webhooks, markdown, threads, commands |
| Slack | 🚧 Skeleton | Events API, mrkdwn, threads |
| Discord | 📋 Planned | — |
| Matrix | 📋 Planned | — |

## AI Backends

Bifrost supports multiple AI backends that can be swapped via configuration:

| Backend | Status | Description |
|---------|--------|-------------|
| `norns` | ✅ Default | Hliðskjálf Norns via LangGraph API |
| `openai` | ✅ Ready | Direct OpenAI GPT models |
| `anthropic` | ✅ Ready | Direct Anthropic Claude models |
| `mcp` | ✅ Ready | Any MCP-compatible server |

### Switching Backends

```bash
# Use Norns (default)
AI_BACKEND=norns

# Use OpenAI directly
AI_BACKEND=openai
OPENAI_API_KEY=sk-...

# Use Claude directly  
AI_BACKEND=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Use any MCP server
AI_BACKEND=mcp
MCP_SERVER_URL=http://localhost:3000
```

## Quick Start

### 1. Create Your Telegram Bot

1. Open Telegram and message [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Get Your Telegram User ID

Message [@userinfobot](https://t.me/userinfobot) — it replies with your ID.

### 3. Configure & Run

```bash
cd bifrost-gateway

# Interactive setup
./scripts/setup.sh

# Or manually create .env:
cat > .env << EOF
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_WEBHOOK_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
TELEGRAM_ALLOWED_USERS=your-user-id
EOF

# Start
docker-compose up -d
```

### 4. Expose to Internet

```bash
# Option A: ngrok (quick testing)
ngrok http 8050

# Option B: Cloudflare Tunnel (production)
cloudflared tunnel --url http://localhost:8050
```

### 5. Set Webhook

```bash
curl -X POST "http://localhost:8050/webhook/telegram/set?url=https://YOUR_URL/webhook/telegram/YOUR_SECRET"
```

### 6. Test It!

Message your bot on Telegram! 🎉

## API Endpoints

### Core

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/adapters` | GET | List all adapters and their status |

### Telegram

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/telegram` | POST | Webhook (no secret) |
| `/webhook/telegram/{secret}` | POST | Webhook (with secret) |
| `/webhook/telegram/info` | GET | Get webhook info |
| `/webhook/telegram/set?url=` | POST | Set webhook URL |
| `/webhook/telegram` | DELETE | Remove webhook |

### Generic

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/{adapter_name}` | POST | Generic webhook for any adapter |

## Commands (Telegram)

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show commands |
| `/wisdom` | Get Norns wisdom |
| `/reset` | Clear conversation |
| `/status` | Check connectivity |

## Adding New Adapters

Bifrost uses an extensible adapter pattern. To add a new platform:

1. Create `src/adapters/myplatform.py`
2. Implement `BaseAdapter` interface
3. Use `@register_adapter("myplatform")` decorator
4. Add config in `config.py`
5. Add webhook route in `main.py`

See **[RUNBOOK-020: Add Bifrost Adapter](../docs/runbooks/RUNBOOK-020-add-bifrost-adapter.md)** for detailed instructions.

## Adding New AI Backends

Bifrost uses an extensible backend pattern. To add a new AI system:

1. Create `src/backends/mybackend.py`
2. Implement `BaseBackend` interface
3. Use `@register_backend("mybackend")` decorator
4. Add config in `config.py`

See **[RUNBOOK-021: Add Bifrost AI Backend](../docs/runbooks/RUNBOOK-021-add-bifrost-ai-backend.md)** for detailed instructions.

### Backend Interface

```python
from src.backends.base import BaseBackend, register_backend

@register_backend("mybackend")
class MyBackend(BaseBackend):
    @property
    def name(self) -> str:
        return "mybackend"
    
    @property
    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(...)
    
    async def initialize(self) -> None:
        # Setup connections
        pass
    
    async def shutdown(self) -> None:
        # Cleanup
        pass
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        # Process message and return response
        return ChatResponse(content="Hello!", thread_id="123")
```

### Adapter Interface

```python
from src.adapters.base import BaseAdapter, register_adapter

@register_adapter("myplatform")
class MyAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "myplatform"
    
    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(...)
    
    async def initialize(self) -> None:
        # Setup connections
        pass
    
    async def shutdown(self) -> None:
        # Cleanup
        pass
    
    async def handle_webhook(self, payload: dict) -> bool:
        # Process incoming webhook
        message = self._parse(payload)
        response = await self.message_handler(message)
        await self.send_response(message, response)
        return True
    
    async def send_response(self, original, response) -> bool:
        # Send to platform
        return True
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| **Core** | | |
| `APP_ENV` | development | Environment name |
| `DEBUG` | false | Enable debug logging |
| `REDIS_URL` | redis://redis:6379/3 | Redis for state |
| **Norns** | | |
| `NORNS_API_URL` | http://hlidskjalf:8900 | Direct API |
| `NORNS_LANGGRAPH_URL` | http://langgraph:2024 | LangGraph API |
| `USE_LANGGRAPH` | true | Use LangGraph API |
| **Telegram** | | |
| `TELEGRAM_ENABLED` | true | Enable adapter |
| `TELEGRAM_BOT_TOKEN` | — | Bot token from BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | — | Secret for webhook URL |
| `TELEGRAM_ALLOWED_USERS` | — | Comma-separated user IDs |
| `TELEGRAM_RATE_LIMIT_MESSAGES` | 30 | Max messages per window |
| `TELEGRAM_RATE_LIMIT_WINDOW` | 60 | Window in seconds |
| **Slack** | | |
| `SLACK_ENABLED` | false | Enable adapter |
| `SLACK_BOT_TOKEN` | — | Bot OAuth token |
| `SLACK_SIGNING_SECRET` | — | Signing secret |

## Security

1. **User Whitelist** — Set `*_ALLOWED_USERS` to restrict access
2. **Webhook Secrets** — Use `*_WEBHOOK_SECRET` for URL validation
3. **Network Isolation** — Only Bifrost is exposed to internet
4. **Rate Limiting** — Prevents abuse (Redis-backed)

## Project Structure

```
bifrost-gateway/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── README.md
├── scripts/
│   └── setup.sh
└── src/
    ├── __init__.py
    ├── config.py              # Configuration management
    ├── main.py                # FastAPI application
    ├── adapters/              # Messaging platform integrations
    │   ├── __init__.py
    │   ├── base.py            # BaseAdapter interface
    │   ├── registry.py        # Adapter registration
    │   ├── telegram.py        # Telegram implementation
    │   └── slack.py           # Slack skeleton
    └── backends/              # AI system integrations
        ├── __init__.py
        ├── base.py            # BaseBackend interface
        ├── registry.py        # Backend registration
        ├── norns.py           # Norns/LangGraph backend
        ├── openai_backend.py  # Direct OpenAI
        ├── anthropic_backend.py # Direct Claude
        └── mcp_backend.py     # MCP protocol
```

## Troubleshooting

### Adapter not appearing?
```bash
curl http://localhost:8050/adapters
docker logs bifrost-gateway
```

### Webhooks not working?
1. Check tunnel is running (ngrok/cloudflared)
2. Verify webhook is set: `curl http://localhost:8050/webhook/telegram/info`
3. Check Telegram requires HTTPS

### "Unauthorized" messages?
Your user ID isn't in `TELEGRAM_ALLOWED_USERS`. Get ID from @userinfobot.

---

*"Bifrost, the rainbow bridge, stretches from Midgard to Asgard, guarded by Heimdall who sees all."*

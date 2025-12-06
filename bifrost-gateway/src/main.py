"""
Bifrost Gateway — Main Application

The rainbow bridge connecting external services to AI backends.
Uses extensible adapter and backend patterns for multi-platform support.
"""

from __future__ import annotations

import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import make_asgi_app

from src.config import get_settings
from src.adapters import (
    AdapterMessage,
    AdapterResponse,
    get_adapter,
    get_enabled_adapters,
    initialize_adapters,
    shutdown_adapters,
)
from src.adapters.registry import list_registered_adapters, set_message_handler_for_all
from src.backends import (
    ChatRequest,
    get_active_backend,
    initialize_backend,
    shutdown_backend,
)
from src.backends.registry import list_registered_backends
from src.gitlab_client import GitLabClient
from src.secrets import get_secrets_helper
from src.work_items import (
    WORK_QUEUE,
    WorkItem,
    WorkItemPoller,
    WorkItemProcessor,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if get_settings().DEBUG else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

_gitlab_client: GitLabClient | None = None
_work_item_processor: WorkItemProcessor | None = None
_work_item_poller: WorkItemPoller | None = None
_gitlab_webhook_secret: str | None = None


async def handle_adapter_message(message: AdapterMessage) -> AdapterResponse:
    """
    Universal message handler for all adapters.
    
    Routes messages from any adapter to the active AI backend.
    """
    backend = get_active_backend()
    
    if backend is None or not backend.is_initialized:
        return AdapterResponse(
            content="⚠️ Bifrost has no active AI backend. Check configuration.",
            current_norn="verdandi",
        )
    
    # Handle special commands
    if message.message_type == "command":
        if message.content == "/wisdom":
            wisdom = await backend.get_wisdom()
            return AdapterResponse(
                content=wisdom,
                current_norn="verdandi",
                parse_mode="markdown",
            )
    
    # Regular message - send to backend
    request = ChatRequest(
        message=message.content,
        thread_id=message.thread_id,
        user_id=message.user_id,
        channel_id=message.channel_id,
        adapter_name=message.adapter_name,
    )
    
    response = await backend.chat(request)
    
    # Detect persona (for Norns-style responses)
    persona = backend.detect_response_persona(response.content)
    
    return AdapterResponse(
        content=response.content,
        current_norn=response.current_norn or persona,
        norns_thread_id=response.thread_id,
        parse_mode="markdown",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()
    global _gitlab_client, _work_item_processor, _work_item_poller, _gitlab_webhook_secret
    logger.info(
        "bifrost_starting",
        app=settings.APP_NAME,
        env=settings.APP_ENV,
        registered_adapters=list_registered_adapters(),
        registered_backends=list_registered_backends(),
    )
    
    # Initialize the selected AI backend
    backend_config = settings.get_active_backend_config()
    await initialize_backend(settings.AI_BACKEND, backend_config)
    
    # Initialize all enabled adapters
    adapter_configs = settings.get_enabled_adapter_configs()
    await initialize_adapters(adapter_configs)
    
    # Set the message handler for all adapters
    set_message_handler_for_all(handle_adapter_message)
    
    # Log status
    backend = get_active_backend()
    enabled_adapters = get_enabled_adapters()
    logger.info(
        "bifrost_ready",
        backend=backend.name if backend else "none",
        enabled_adapters=list(enabled_adapters.keys()),
    )
    
    # GitLab → Norns integration (optional if secrets available)
    secrets_helper = get_secrets_helper(
        endpoint_url=settings.AWS_ENDPOINT_URL,
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

    gitlab_token = settings.GITLAB_PAT
    if not gitlab_token and settings.GITLAB_PAT_SECRET_NAME:
        secret_payload = secrets_helper.get_secret_json(settings.GITLAB_PAT_SECRET_NAME)
        gitlab_token = secret_payload.get("token")

    _gitlab_webhook_secret = settings.GITLAB_WEBHOOK_SECRET
    if not _gitlab_webhook_secret and settings.GITLAB_WEBHOOK_SECRET_NAME:
        try:
            _gitlab_webhook_secret = secrets_helper.get_secret(settings.GITLAB_WEBHOOK_SECRET_NAME)
        except Exception as exc:  # pragma: no cover - logs for ops
            logger.warning("gitlab_webhook_secret_missing", error=str(exc))

    if gitlab_token:
        _gitlab_client = GitLabClient(settings.GITLAB_BASE_URL, gitlab_token)
        _work_item_processor = WorkItemProcessor(_gitlab_client, settings.GITLAB_PROJECT_ID)
        _work_item_processor.start()

        _work_item_poller = WorkItemPoller(
            _gitlab_client,
            settings.GITLAB_PROJECT_ID,
            interval_seconds=settings.WORKQUEUE_POLL_INTERVAL_SECONDS,
        )
        _work_item_poller.start()
        logger.info("gitlab_workqueue_enabled", project_id=settings.GITLAB_PROJECT_ID)
    else:
        logger.warning("gitlab_token_missing", message="Work queue disabled")

    yield
    
    # Shutdown
    logger.info("bifrost_shutting_down")
    await shutdown_adapters()
    await shutdown_backend()
    if _work_item_poller:
        await _work_item_poller.stop()
    if _work_item_processor:
        await _work_item_processor.stop()
    if _gitlab_client:
        await _gitlab_client.close()


# Create FastAPI app
app = FastAPI(
    title="Bifrost Gateway",
    description="The rainbow bridge connecting external services to AI backends",
    version="0.3.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# =============================================================================
# MODELS
# =============================================================================

class HealthResponse(BaseModel):
    status: str
    service: str
    backend: str
    enabled_adapters: list[str]


class AdapterStatus(BaseModel):
    name: str
    enabled: bool
    initialized: bool
    capabilities: dict


class BackendStatus(BaseModel):
    name: str
    enabled: bool
    initialized: bool
    capabilities: dict


# =============================================================================
# CORE ROUTES
# =============================================================================

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint — basic health check."""
    backend = get_active_backend()
    return HealthResponse(
        status="ok",
        service=get_settings().APP_NAME,
        backend=backend.name if backend else "none",
        enabled_adapters=list(get_enabled_adapters().keys()),
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    backend = get_active_backend()
    return HealthResponse(
        status="ok",
        service=get_settings().APP_NAME,
        backend=backend.name if backend else "none",
        enabled_adapters=list(get_enabled_adapters().keys()),
    )


@app.get("/adapters")
async def list_adapters():
    """List all registered and enabled adapters."""
    adapters = []
    enabled = get_enabled_adapters()
    
    for name in list_registered_adapters():
        adapter = enabled.get(name)
        if adapter:
            adapters.append(AdapterStatus(
                name=name,
                enabled=True,
                initialized=adapter.is_initialized,
                capabilities=adapter.capabilities.__dict__,
            ))
        else:
            adapters.append(AdapterStatus(
                name=name,
                enabled=False,
                initialized=False,
                capabilities={},
            ))
    
    return {"adapters": adapters}


@app.get("/backends")
async def list_backends():
    """List all registered backends and the active one."""
    active = get_active_backend()
    backends = []
    
    for name in list_registered_backends():
        if active and active.name == name:
            backends.append(BackendStatus(
                name=name,
                enabled=True,
                initialized=active.is_initialized,
                capabilities=active.capabilities.__dict__,
            ))
        else:
            backends.append(BackendStatus(
                name=name,
                enabled=False,
                initialized=False,
                capabilities={},
            ))
    
    return {
        "active": active.name if active else None,
        "backends": backends,
    }


# =============================================================================
# TELEGRAM ROUTES
# =============================================================================

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Telegram webhook endpoint (no secret)."""
    adapter = get_adapter("telegram")
    if not adapter or not adapter.is_enabled:
        raise HTTPException(status_code=503, detail="Telegram adapter not enabled")
    
    try:
        payload = await request.json()
        logger.debug("telegram_webhook", update_id=payload.get("update_id"))
        success = await adapter.handle_webhook(payload)
        return {"ok": success}
    except Exception as e:
        logger.error("telegram_webhook_error", error=str(e))
        return {"ok": False, "error": str(e)}


@app.post("/webhook/telegram/{secret}")
async def telegram_webhook_with_secret(secret: str, request: Request):
    """Telegram webhook endpoint with secret validation."""
    adapter = get_adapter("telegram")
    if not adapter or not adapter.is_enabled:
        raise HTTPException(status_code=503, detail="Telegram adapter not enabled")
    
    if not adapter.verify_webhook(secret, b""):
        logger.warning("telegram_invalid_secret")
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    
    try:
        payload = await request.json()
        success = await adapter.handle_webhook(payload)
        return {"ok": success}
    except Exception as e:
        logger.error("telegram_webhook_error", error=str(e))
        return {"ok": False, "error": str(e)}


@app.get("/webhook/telegram/info")
async def telegram_webhook_info():
    """Get Telegram webhook info."""
    adapter = get_adapter("telegram")
    if not adapter or not adapter.is_enabled:
        raise HTTPException(status_code=503, detail="Telegram adapter not enabled")
    
    from src.adapters.telegram import TelegramAdapter
    if isinstance(adapter, TelegramAdapter):
        return await adapter.get_webhook_info()
    
    raise HTTPException(status_code=500, detail="Invalid adapter type")


@app.post("/webhook/telegram/set")
async def telegram_set_webhook(url: str):
    """Set Telegram webhook URL."""
    adapter = get_adapter("telegram")
    if not adapter or not adapter.is_enabled:
        raise HTTPException(status_code=503, detail="Telegram adapter not enabled")
    
    from src.adapters.telegram import TelegramAdapter
    if isinstance(adapter, TelegramAdapter):
        success = await adapter.set_webhook(url)
        if success:
            return {"ok": True, "url": url}
        raise HTTPException(status_code=500, detail="Failed to set webhook")
    
    raise HTTPException(status_code=500, detail="Invalid adapter type")


@app.delete("/webhook/telegram")
async def telegram_delete_webhook():
    """Delete Telegram webhook."""
    adapter = get_adapter("telegram")
    if not adapter or not adapter.is_enabled:
        raise HTTPException(status_code=503, detail="Telegram adapter not enabled")
    
    from src.adapters.telegram import TelegramAdapter
    if isinstance(adapter, TelegramAdapter):
        success = await adapter.delete_webhook()
        if success:
            return {"ok": True}
        raise HTTPException(status_code=500, detail="Failed to delete webhook")
    
    raise HTTPException(status_code=500, detail="Invalid adapter type")


# =============================================================================
# SLACK ROUTES
# =============================================================================

@app.post("/webhook/slack")
async def slack_webhook(request: Request):
    """Slack events webhook endpoint."""
    adapter = get_adapter("slack")
    if not adapter or not adapter.is_enabled:
        raise HTTPException(status_code=503, detail="Slack adapter not enabled")
    
    payload = await request.json()
    
    # Handle Slack URL verification
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    
    success = await adapter.handle_webhook(payload)
    return {"ok": success}


# =============================================================================
# GENERIC ADAPTER ROUTE
# =============================================================================

@app.post("/webhook/{adapter_name}")
async def generic_webhook(adapter_name: str, request: Request):
    """Generic webhook endpoint for any registered adapter."""
    adapter = get_adapter(adapter_name)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Adapter '{adapter_name}' not found")
    if not adapter.is_enabled:
        raise HTTPException(status_code=503, detail=f"Adapter '{adapter_name}' not enabled")
    
    try:
        payload = await request.json()
        success = await adapter.handle_webhook(payload)
        return {"ok": success}
    except Exception as e:
        logger.error("generic_webhook_error", adapter=adapter_name, error=str(e))
        return {"ok": False, "error": str(e)}


# =============================================================================
# DIRECT CHAT API (for testing/debugging)
# =============================================================================

class DirectChatRequest(BaseModel):
    message: str
    thread_id: str = None


class DirectChatResponse(BaseModel):
    content: str
    thread_id: str
    backend: str


@app.post("/chat", response_model=DirectChatResponse)
async def direct_chat(request: DirectChatRequest):
    """
    Direct chat endpoint for testing without going through an adapter.
    
    Useful for debugging the AI backend connection.
    """
    backend = get_active_backend()
    if not backend or not backend.is_initialized:
        raise HTTPException(status_code=503, detail="No active AI backend")
    
    chat_request = ChatRequest(
        message=request.message,
        thread_id=request.thread_id,
    )
    
    response = await backend.chat(chat_request)
    
    return DirectChatResponse(
        content=response.content,
        thread_id=response.thread_id,
        backend=backend.name,
    )


# =============================================================================
# GitLab → Norns work queue webhook
# =============================================================================

@app.post("/api/work-items")
async def work_item_webhook(request: Request):
    """Receive GitLab issue hooks and enqueue Norns work items."""
    if not _gitlab_client or not _work_item_processor:
        raise HTTPException(status_code=503, detail="Work queue not initialized")

    expected_token = _gitlab_webhook_secret
    provided_token = request.headers.get("X-Gitlab-Token")
    if expected_token and provided_token != expected_token:
        logger.warning("gitlab_webhook_invalid_token")
        raise HTTPException(status_code=403, detail="Invalid token")

    event_name = request.headers.get("X-Gitlab-Event", "")
    if event_name not in {"Issue Hook", "Confidential Issue Hook"}:
        return {"status": "ignored", "reason": "unsupported_event"}

    payload = await request.json()
    issue_attrs = payload.get("object_attributes") or {}
    issue_id = issue_attrs.get("id")
    issue_iid = issue_attrs.get("iid")

    if not issue_id or not issue_iid:
        raise HTTPException(status_code=400, detail="Missing issue identifiers")

    labels: list[str] = []
    for label in payload.get("labels", []):
        if isinstance(label, dict) and label.get("title"):
            labels.append(label["title"])
        elif isinstance(label, str):
            labels.append(label)

    if "actor::norns" not in labels or "workflow::ready" not in labels:
        return {"status": "ignored", "reason": "label_gate"}

    item = WorkItem(
        project_id=get_settings().GITLAB_PROJECT_ID,
        issue_id=issue_id,
        issue_iid=issue_iid,
        title=issue_attrs.get("title", "Untitled"),
        description=issue_attrs.get("description") or "",
        labels=labels,
        web_url=issue_attrs.get("url") or issue_attrs.get("web_url") or "",
        updated_at=issue_attrs.get("updated_at") or "",
        author=(payload.get("user") or {}).get("username"),
        assigned_to=(issue_attrs.get("assignee") or {}).get("username"),
        payload=payload,
        source="webhook",
    )

    await WORK_QUEUE.enqueue(item)
    return {"status": "queued", "issue": issue_iid}


# =============================================================================
# ENTRYPOINT
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

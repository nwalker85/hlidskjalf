from __future__ import annotations

from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
import structlog

from .config import get_settings
from .gitlab_client import GitLabService
from .secrets import resolve_gitlab_tokens, resolve_zitadel_credentials
from .tools import build_tool_registry, ToolContext
from .zitadel_client import ZitadelService
from .docker_client import DockerService
from .auth import require_oauth_token

logger = structlog.get_logger(__name__)
settings = get_settings()
app = FastAPI(title="MCP GitLab Server")


def _init_clients() -> tuple[ToolContext, list, dict]:
    token, _wiki_token = resolve_gitlab_tokens(settings)
    if not token:
        raise RuntimeError(
            "GitLab MCP token not configured. Provide GITLAB_MCP_TOKEN "
            "or create the ravenhelm/dev/gitlab/mcp_service secret."
        )
    gitlab_service = GitLabService(settings, token)
    zitadel_service = None
    try:
        zitadel_creds = resolve_zitadel_credentials(settings)
        zitadel_token = zitadel_creds.get("token")
        if zitadel_token:
            zitadel_service = ZitadelService(settings, zitadel_token)
            logger.info("zitadel_client_initialized")
    except Exception as exc:  # noqa: BLE001
        logger.warning("zitadel_client_init_failed", error=str(exc))

    docker_service = None
    try:
        docker_service = DockerService(settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("docker_client_init_failed", error=str(exc))

    context = ToolContext(
        settings=settings,
        gitlab=gitlab_service,
        zitadel=zitadel_service,
        docker=docker_service,
    )
    tools, tool_map = build_tool_registry(context)
    return context, tools, tool_map


TOOL_CONTEXT, TOOL_LIST, TOOL_MAP = _init_clients()


@app.get("/healthz")
async def healthcheck():
    return {"status": "ok", "service": settings.app_name}


@app.get("/healthz/gitlab")
async def gitlab_healthcheck():
    try:
        user = TOOL_CONTEXT.gitlab.get_authenticated_user()
        return {"status": "ok", "user": user}
    except Exception as exc:  # noqa: BLE001
        logger.error("gitlab_health_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="GitLab authentication failed")


@app.post("/tools/list")
async def list_tools(_: dict = Depends(require_oauth_token)):
    payload = [
        {"name": tool.name, "description": tool.description, "schema": tool.schema}
        for tool in TOOL_LIST
    ]
    return {"tools": payload}


@app.post("/tools/call")
async def call_tool(
    request: Dict[str, Any],
    claims: Dict[str, Any] = Depends(require_oauth_token),
):
    name = request.get("name")
    arguments = request.get("arguments") or {}

    if name not in TOOL_MAP:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")

    tool = TOOL_MAP[name]
    if not tool.handler:
        raise HTTPException(status_code=400, detail="Tool handler not implemented")

    try:
        result = tool.handler(TOOL_CONTEXT, arguments)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("tool_call_failed", tool=name, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

    logger.info(
        "mcp_tool_call",
        tool=name,
        subject=claims.get("sub"),
        scopes=claims.get("scope"),
        result_status=result.get("status"),
    )

    return JSONResponse({"content": result})


@app.post("/resources/list")
async def list_resources(_: dict = Depends(require_oauth_token)):
    """No resources yet."""
    return {"resources": []}


@app.post("/resources/read")
async def read_resource(
    request: Dict[str, Any],
    _: dict = Depends(require_oauth_token),
):
    raise HTTPException(status_code=404, detail="No resources implemented yet")


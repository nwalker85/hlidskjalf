from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from . import ToolContext


def _require_docker(ctx: "ToolContext"):
    if not ctx.docker:
        raise HTTPException(
            status_code=400,
            detail="Docker integration is not available (socket missing?).",
        )
    return ctx.docker


def list_containers_tool(ctx: "ToolContext", arguments: Dict[str, Any]) -> Dict[str, Any]:
    docker_service = _require_docker(ctx)
    try:
        containers = docker_service.list_containers(
            status=arguments.get("status"),
            label=arguments.get("label"),
            name=arguments.get("name"),
        )
        return {"containers": containers}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def container_stats_tool(ctx: "ToolContext", arguments: Dict[str, Any]) -> Dict[str, Any]:
    docker_service = _require_docker(ctx)
    container_id = arguments.get("container_id")
    if not container_id:
        raise HTTPException(status_code=400, detail="'container_id' is required")
    try:
        stats = docker_service.get_stats(container_id)
        return {"stats": stats}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


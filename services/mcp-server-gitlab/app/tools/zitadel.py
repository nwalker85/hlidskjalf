from __future__ import annotations

from typing import Dict, Any, TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from . import ToolContext


def _require_zitadel(ctx: "ToolContext"):
    if not ctx.zitadel:
        raise HTTPException(
            status_code=400,
            detail="Zitadel integration is not configured for this MCP server.",
        )
    return ctx.zitadel


def list_user_roles_tool(ctx: "ToolContext", arguments: Dict[str, Any]) -> Dict[str, Any]:
    service = _require_zitadel(ctx)
    user_id = arguments.get("user_id")
    email = arguments.get("email")
    if not user_id and not email:
        raise HTTPException(
            status_code=400, detail="Provide either 'user_id' or 'email' to list roles."
        )
    try:
        return service.list_user_roles(user_id=user_id, email=email)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def assign_user_roles_tool(ctx: "ToolContext", arguments: Dict[str, Any]) -> Dict[str, Any]:
    service = _require_zitadel(ctx)
    role_keys = arguments.get("role_keys") or []
    if not isinstance(role_keys, list) or not role_keys:
        raise HTTPException(status_code=400, detail="'role_keys' must be a non-empty list")
    try:
        return service.assign_roles(
            user_id=arguments.get("user_id"),
            email=arguments.get("email"),
            role_keys=role_keys,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def create_service_account_tool(
    ctx: "ToolContext", arguments: Dict[str, Any]
) -> Dict[str, Any]:
    service = _require_zitadel(ctx)
    user_name = arguments.get("user_name")
    if not user_name:
        raise HTTPException(status_code=400, detail="'user_name' is required")

    try:
        return service.create_service_account(
            user_name=user_name,
            display_name=arguments.get("display_name"),
            description=arguments.get("description"),
            role_keys=arguments.get("role_keys"),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


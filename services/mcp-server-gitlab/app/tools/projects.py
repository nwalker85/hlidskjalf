from __future__ import annotations

from typing import Any, Dict

from ..gitlab_client import GitLabService


def create_project_tool(client: GitLabService, arguments: Dict[str, Any]) -> Dict[str, Any]:
    name = arguments.get("name")
    group = arguments.get("group_path")
    if not name or not group:
        return {"status": "error", "message": "name and group_path are required"}

    visibility = arguments.get("visibility", "private")
    description = arguments.get("description")
    template_project_id = arguments.get("template_project_id")

    result = client.ensure_project(
        name=name,
        group_path=group,
        visibility=visibility,
        description=description,
        template_project_id=template_project_id,
    )
    return {
        "status": result["status"],
        "project_id": result.get("project_id"),
        "web_url": result.get("web_url"),
    }


def add_project_hook_tool(client: GitLabService, arguments: Dict[str, Any]) -> Dict[str, Any]:
    project_path = arguments.get("project_path")
    url = arguments.get("url")
    events = arguments.get("events") or ["push_events"]

    if not project_path or not url:
        return {"status": "error", "message": "project_path and url are required"}

    secret_token = arguments.get("token")
    result = client.add_webhook(project_path, url, secret_token, events)
    return {
        "status": result["status"],
        "hook_id": result["hook_id"],
    }


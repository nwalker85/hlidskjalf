from __future__ import annotations

from typing import Any, Dict, List

from ..gitlab_client import GitLabService


def list_runners_tool(client: GitLabService, arguments: Dict[str, Any]) -> Dict[str, Any]:
    status = arguments.get("status")
    tags = arguments.get("tag_list") or []
    results = client.list_runners(status=status, tag_list=tags)
    return {
        "status": "ok",
        "count": len(results),
        "runners": results,
    }


def pause_runner_tool(client: GitLabService, arguments: Dict[str, Any]) -> Dict[str, Any]:
    runner_id = arguments.get("runner_id")
    paused = arguments.get("paused", True)
    if not runner_id:
        return {"status": "error", "message": "runner_id is required"}

    result = client.toggle_runner_pause(int(runner_id), bool(paused))
    return {
        "status": "updated",
        "runner_id": result["runner_id"],
        "paused": result["paused"],
        "description": result["description"],
    }


"""
Async GitLab client used by the Norns work-item queue.
"""

from __future__ import annotations

from typing import Any, List

import httpx
import structlog

logger = structlog.get_logger(__name__)


class GitLabClient:
    """Minimal helper for GitLab project + issue operations."""

    def __init__(self, base_url: str, private_token: str) -> None:
        if not base_url.endswith("/"):
            base_url += "/"
        api_base = base_url.rstrip("/") + "/api/v4"
        self._client = httpx.AsyncClient(
            base_url=api_base,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"PRIVATE-TOKEN": private_token},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_issue(self, project_id: int, issue_iid: int) -> dict[str, Any]:
        response = await self._client.get(f"/projects/{project_id}/issues/{issue_iid}")
        response.raise_for_status()
        return response.json()

    async def comment_on_issue(
        self,
        project_id: int,
        issue_iid: int,
        body: str,
    ) -> dict[str, Any]:
        response = await self._client.post(
            f"/projects/{project_id}/issues/{issue_iid}/notes",
            json={"body": body},
        )
        response.raise_for_status()
        return response.json()

    async def update_issue_labels(
        self,
        project_id: int,
        issue_iid: int,
        labels: List[str],
    ) -> dict[str, Any]:
        response = await self._client.put(
            f"/projects/{project_id}/issues/{issue_iid}",
            json={"labels": ",".join(labels)},
        )
        response.raise_for_status()
        return response.json()

    async def list_ready_issues(
        self,
        project_id: int,
        labels: List[str],
        state: str = "opened",
        per_page: int = 50,
    ) -> List[dict[str, Any]]:
        params = {
            "labels": ",".join(labels),
            "state": state,
            "scope": "all",
            "per_page": per_page,
            "order_by": "updated_at",
            "sort": "desc",
        }
        response = await self._client.get(f"/projects/{project_id}/issues", params=params)
        response.raise_for_status()
        return response.json()


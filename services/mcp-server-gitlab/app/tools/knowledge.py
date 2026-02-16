from __future__ import annotations

from typing import Any, Dict

import structlog

from ..gitlab_client import GitLabService

logger = structlog.get_logger(__name__)


def list_wiki_pages(client: GitLabService, project_path: str) -> Dict[str, Any]:
    try:
        project = client.get_project(project_path)
        pages = project.wikis.list(get_all=True)
    except Exception as exc:  # noqa: BLE001
        logger.error("wiki_list_failed", error=str(exc))
        return {"status": "error", "message": str(exc)}

    result = [
        {
            "slug": page.slug,
            "title": page.title,
            "format": page.format,
            "updated_at": page.updated_at,
        }
        for page in pages
    ]
    return {
        "status": "ok",
        "count": len(result),
        "pages": result,
    }


def docs_sync_status(
    wiki_summary: Dict[str, Any],
    reference_doc: str,
) -> Dict[str, Any]:
    """Return a status stub explaining manual process."""
    message = (
        "Knowledge base automation is currently staged-only. "
        "Refer to docs/KNOWLEDGE_AND_PROCESS.md for the doc→wiki mapping. "
        "Once the GitLab MR workflow is finalized, this tool will open merge requests "
        "rather than pushing directly."
    )
    return {
        "status": "manual-review",
        "message": message,
        "wiki_pages": wiki_summary.get("count", 0),
        "reference_doc": reference_doc,
    }


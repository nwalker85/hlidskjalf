"""
Work-item queue + metrics for GitLab → Norns automation.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog
from prometheus_client import Counter, Gauge

from src.backends import ChatRequest, get_active_backend
from src.gitlab_client import GitLabClient

logger = structlog.get_logger(__name__)

WORK_ITEMS_RECEIVED = Counter(
    "norns_work_items_received_total",
    "Total GitLab issues routed to the Norns work queue",
    ["source"],
)

WORK_ITEMS_PROCESSED = Counter(
    "norns_work_items_processed_total",
    "Total work items processed by the Norns dispatcher",
    ["status"],
)

WORK_QUEUE_DEPTH = Gauge(
    "norns_work_queue_depth",
    "Current number of pending GitLab work items for the Norns",
)

LAST_PROCESSED_TS = Gauge(
    "norns_work_item_last_processed_timestamp",
    "Unix timestamp of the most recent processed work item",
)


@dataclass
class WorkItem:
    project_id: int
    issue_id: int
    issue_iid: int
    title: str
    description: str
    labels: List[str]
    web_url: str
    updated_at: str
    author: Optional[str] = None
    assigned_to: Optional[str] = None
    epic_id: Optional[int] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = "webhook"


class WorkItemQueue:
    """Async queue with simple metrics for visibility."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[WorkItem] = asyncio.Queue()

    async def enqueue(self, item: WorkItem) -> None:
        WORK_ITEMS_RECEIVED.labels(source=item.source).inc()
        await self._queue.put(item)
        WORK_QUEUE_DEPTH.set(self._queue.qsize())
        logger.info(
            "work_item_enqueued",
            issue_iid=item.issue_iid,
            project_id=item.project_id,
            labels=item.labels,
            source=item.source,
        )

    async def dequeue(self) -> WorkItem:
        item = await self._queue.get()
        WORK_QUEUE_DEPTH.set(self._queue.qsize())
        return item


WORK_QUEUE = WorkItemQueue()


class WorkItemProcessor:
    """Background worker that dispatches GitLab issues to the Norns."""

    def __init__(self, gitlab_client: GitLabClient, project_id: int) -> None:
        self._gitlab = gitlab_client
        self._project_id = project_id
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def start(self) -> None:
        if self._task:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="norns-workqueue")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:  # pragma: no cover - expected on shutdown
                pass
        WORK_QUEUE_DEPTH.set(0)

    async def _run(self) -> None:
        while self._running:
            try:
                item = await WORK_QUEUE.dequeue()
                await self._process_item(item)
                WORK_ITEMS_PROCESSED.labels(status="processed").inc()
                LAST_PROCESSED_TS.set(time.time())
            except asyncio.CancelledError:  # pragma: no cover - expected during shutdown
                break
            except Exception as exc:  # pragma: no cover - logged for ops visibility
                logger.error("work_item_processing_failed", error=str(exc))
                WORK_ITEMS_PROCESSED.labels(status="failed").inc()

    async def _process_item(self, item: WorkItem) -> None:
        issue = await self._gitlab.fetch_issue(item.project_id, item.issue_iid)
        labels = {label["title"] for label in issue.get("labels", []) if isinstance(label, dict)}
        labels.update(label for label in issue.get("labels", []) if isinstance(label, str))

        if "workflow::ready" not in labels or "actor::norns" not in labels:
            logger.info(
                "work_item_skipped",
                issue_iid=item.issue_iid,
                reason="labels_no_longer_fit",
            )
            return

        await self._acknowledge_issue(item)
        await self._transition_issue(item, labels)
        await self._notify_norns(item, issue)

    async def _acknowledge_issue(self, item: WorkItem) -> None:
        body = (
            f"🪢 Norns automation acknowledged this work item at {time.strftime('%Y-%m-%d %H:%M:%S %Z')}.\n"
            "Queueing task for processing…"
        )
        await self._gitlab.comment_on_issue(item.project_id, item.issue_iid, body)

    async def _transition_issue(self, item: WorkItem, labels: set[str]) -> None:
        labels.discard("workflow::ready")
        labels.add("workflow::in_progress")
        await self._gitlab.update_issue_labels(item.project_id, item.issue_iid, sorted(labels))

    async def _notify_norns(self, item: WorkItem, issue_payload: dict[str, Any]) -> None:
        backend = get_active_backend()
        if not backend:
            logger.warning("norns_backend_missing", issue=item.issue_iid)
            return

        description = issue_payload.get("description") or "No description provided."
        labels = ", ".join(sorted(item.labels)) or "none"

        message = (
            "New work item assigned to Norns:\n\n"
            f"*Title:* {item.title}\n"
            f"*Issue:* {item.web_url}\n"
            f"*Labels:* {labels}\n\n"
            f"```\n{description[:4000]}\n```"
        )

        thread_id = f"gitlab-issue-{item.issue_iid}"
        request = ChatRequest(
            message=message,
            thread_id=thread_id,
            user_id=item.author or "gitlab",
            channel_id="gitlab-workqueue",
            adapter_name="gitlab",
        )
        response = await backend.chat(request)
        logger.info(
            "norns_notified",
            issue_iid=item.issue_iid,
            thread_id=response.thread_id,
            norn=response.current_norn,
        )


class WorkItemPoller:
    """Fallback poller that reconciles ready issues periodically."""

    def __init__(
        self,
        gitlab_client: GitLabClient,
        project_id: int,
        interval_seconds: int = 180,
        required_labels: Optional[List[str]] = None,
    ) -> None:
        self._gitlab = gitlab_client
        self._project_id = project_id
        self._interval = interval_seconds
        self._required_labels = required_labels or ["actor::norns", "workflow::ready"]
        self._seen: dict[int, str] = {}
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def start(self) -> None:
        if self._task:
            return
        self._running = True
        self._task = asyncio.create_task(self._run(), name="norns-workqueue-poller")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:  # pragma: no cover - expected
                pass

    async def _run(self) -> None:
        while self._running:
            try:
                issues = await self._gitlab.list_ready_issues(
                    self._project_id,
                    labels=self._required_labels,
                )
                for issue in issues:
                    issue_id = issue["id"]
                    updated_at = issue.get("updated_at")
                    if self._seen.get(issue_id) == updated_at:
                        continue
                    self._seen[issue_id] = updated_at
                    await WORK_QUEUE.enqueue(
                        WorkItem(
                            project_id=self._project_id,
                            issue_id=issue_id,
                            issue_iid=issue["iid"],
                            title=issue.get("title", "Untitled"),
                            description=issue.get("description") or "",
                            labels=[label["title"] if isinstance(label, dict) else label for label in issue.get("labels", [])],
                            web_url=issue.get("web_url", ""),
                            updated_at=updated_at or "",
                            author=(issue.get("author") or {}).get("username"),
                            assigned_to=(issue.get("assignee") or {}).get("username"),
                            payload=issue,
                            source="poller",
                        )
                    )
            except asyncio.CancelledError:  # pragma: no cover - expected
                break
            except Exception as exc:  # pragma: no cover - log for ops
                logger.error("work_item_poller_error", error=str(exc))

            await asyncio.sleep(self._interval)


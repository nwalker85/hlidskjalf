from __future__ import annotations

from typing import Any, Dict, List, Optional

import docker
import structlog

from .config import Settings

logger = structlog.get_logger(__name__)


class DockerService:
    """Wrapper around docker SDK with safe read-only helpers."""

    def __init__(self, settings: Settings):
        self._client = docker.DockerClient(base_url=settings.docker_host)

    def list_containers(
        self,
        *,
        status: Optional[str] = None,
        label: Optional[str] = None,
        name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {}
        if status:
            filters["status"] = status
        if label:
            filters.setdefault("label", []).append(label)
        containers = self._client.containers.list(all=True, filters=filters)
        results: List[Dict[str, Any]] = []
        for container in containers:
            if name and name not in container.name:
                continue
            results.append(
                {
                    "id": container.short_id,
                    "name": container.name,
                    "status": container.status,
                    "image": container.image.tags,
                    "labels": container.labels,
                }
            )
        return results

    def get_stats(self, container_id: str) -> Dict[str, Any]:
        container = self._client.containers.get(container_id)
        stats = container.stats(stream=False)

        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats[
            "precpu_stats"
        ]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"][
            "system_cpu_usage"
        ]
        cpu_percent = 0.0
        if system_delta > 0.0 and cpu_delta > 0.0:
            cpu_percent = (cpu_delta / system_delta) * len(
                stats["cpu_stats"]["cpu_usage"].get("percpu_usage", []) or [1]
            ) * 100.0

        mem_usage = stats["memory_stats"].get("usage", 0)
        mem_limit = stats["memory_stats"].get("limit", 1)
        mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit else 0.0

        return {
            "id": container.short_id,
            "name": container.name,
            "status": container.status,
            "cpu_percent": round(cpu_percent, 2),
            "memory_mb": round(mem_usage / (1024 * 1024), 2),
            "memory_percent": round(mem_percent, 2),
            "pids": stats.get("pids_stats", {}).get("current"),
        }


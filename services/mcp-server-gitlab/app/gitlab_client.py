from __future__ import annotations

from typing import Any, Dict, List

import gitlab
import structlog

from .config import Settings

logger = structlog.get_logger(__name__)


class GitLabService:
    """Wrapper around python-gitlab with helper utilities."""

    def __init__(self, settings: Settings, token: str):
        self._settings = settings
        api_url = settings.gitlab_api_url or settings.gitlab_base_url
        self._client = gitlab.Gitlab(
            url=api_url,
            private_token=token,
            ssl_verify=settings.gitlab_verify_ssl,
        )
        try:
            self._client.auth()
            logger.info("gitlab_auth_success")
        except Exception as exc:  # noqa: BLE001
            logger.warning("gitlab_auth_failed", error=str(exc))

        self._project_cache: Dict[str, gitlab.v4.objects.Project] = {}

    # --------------------------------------------------------------------- #
    # Helper methods
    # --------------------------------------------------------------------- #
    def get_group(self, group_path: str):
        return self._client.groups.get(group_path)

    def get_project(self, project_path: str):
        if project_path in self._project_cache:
            return self._project_cache[project_path]
        project = self._client.projects.get(project_path)
        self._project_cache[project_path] = project
        return project

    # --------------------------------------------------------------------- #
    # Projects
    # --------------------------------------------------------------------- #
    def ensure_project(
        self,
        name: str,
        group_path: str,
        visibility: str = "private",
        description: str | None = None,
        template_project_id: int | None = None,
    ) -> Dict[str, Any]:
        path = f"{group_path}/{name}"
        try:
            project = self.get_project(path)
            return {
                "status": "exists",
                "message": f"Project {path} already exists.",
                "project_id": project.id,
                "web_url": self._external_url(project.web_url),
            }
        except gitlab.exceptions.GitlabGetError:
            pass

        group = self.get_group(group_path)
        payload = {
            "name": name,
            "path": name.lower().replace(" ", "-"),
            "namespace_id": group.id,
            "visibility": visibility,
        }
        if description:
            payload["description"] = description
        if template_project_id:
            payload["use_custom_template"] = True
            payload["template_project_id"] = template_project_id

        project = self._client.projects.create(payload)
        self._project_cache[path] = project
        return {
            "status": "created",
            "project_id": project.id,
            "web_url": self._external_url(project.web_url),
        }

    def add_webhook(
        self,
        project_path: str,
        url: str,
        token: str | None,
        events: List[str],
    ) -> Dict[str, Any]:
        project = self.get_project(project_path)
        hooks = project.hooks.list()
        for hook in hooks:
            if hook.url == url:
                hook.events = {event: True for event in events}
                hook.token = token or hook.token
                hook.save()
                return {"status": "updated", "hook_id": hook.id}

        hook = project.hooks.create(
            {
                "url": url,
                "token": token,
                **{event: True for event in events},
            }
        )
        return {"status": "created", "hook_id": hook.id}

    # --------------------------------------------------------------------- #
    # Runners
    # --------------------------------------------------------------------- #
    def list_runners(
        self,
        status: str | None = None,
        tag_list: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"all": True}
        if status:
            params["status"] = status
        runners = self._client.runners.list(**params)
        results = []
        for runner in runners:
            tags = runner.tag_list or []
            if tag_list and not set(tag_list).issubset(set(tags)):
                continue
            results.append(
                {
                    "id": runner.id,
                    "description": runner.description,
                    "online": runner.online,
                    "status": runner.status,
                    "tag_list": tags,
                    "paused": runner.paused,
                }
            )
        return results

    def toggle_runner_pause(self, runner_id: int, paused: bool) -> Dict[str, Any]:
        runner = self._client.runners.get(runner_id)
        runner.paused = paused
        runner.save()
        return {
            "runner_id": runner.id,
            "paused": runner.paused,
            "description": runner.description,
        }

    def get_authenticated_user(self) -> Dict[str, Any]:
        """Return metadata about the GitLab user backing this PAT."""
        user = getattr(self._client, "user", None)
        if user is None:
            user = self._client.users.get("self")
        return {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "state": user.state,
        }

    # --------------------------------------------------------------------- #
    def _external_url(self, url: str | None) -> str | None:
        if not url:
            return None
        internal = (self._client.url or "").rstrip("/")
        external = self._settings.gitlab_base_url.rstrip("/")
        return url.replace(internal, external, 1)


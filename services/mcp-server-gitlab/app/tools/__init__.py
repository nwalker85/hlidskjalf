from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from ..config import Settings
from ..gitlab_client import GitLabService
from ..zitadel_client import ZitadelService
from ..docker_client import DockerService
from .knowledge import docs_sync_status, list_wiki_pages
from .projects import add_project_hook_tool, create_project_tool
from .runners import list_runners_tool, pause_runner_tool
from .zitadel import (
    assign_user_roles_tool,
    create_service_account_tool,
    list_user_roles_tool,
)
from .docker_tools import list_containers_tool, container_stats_tool


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: Dict[str, Any]
    handler: Callable[["ToolContext", Dict[str, Any]], Dict[str, Any]] | None = None


@dataclass
class ToolContext:
    settings: Settings
    gitlab: GitLabService
    zitadel: ZitadelService | None = None
    docker: DockerService | None = None


def build_tool_registry(context: ToolContext):
    """Return tool specs and callables."""

    tools: List[ToolSpec] = [
        ToolSpec(
            name="gitlab.projects.create",
            description="Create a GitLab project in the specified group (idempotent).",
            schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "group_path": {"type": "string"},
                    "visibility": {"type": "string", "enum": ["private", "public", "internal"]},
                    "description": {"type": "string"},
                    "template_project_id": {"type": "integer"},
                },
                "required": ["name", "group_path"],
            },
            handler=lambda ctx, args: create_project_tool(ctx.gitlab, args),
        ),
        ToolSpec(
            name="gitlab.projects.add_webhook",
            description="Create or update a project webhook.",
            schema={
                "type": "object",
                "properties": {
                    "project_path": {"type": "string"},
                    "url": {"type": "string"},
                    "token": {"type": "string"},
                    "events": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["push_events"],
                    },
                },
                "required": ["project_path", "url"],
            },
            handler=lambda ctx, args: add_project_hook_tool(ctx.gitlab, args),
        ),
        ToolSpec(
            name="gitlab.runners.list",
            description="List GitLab runners with optional filters.",
            schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "tag_list": {"type": "array", "items": {"type": "string"}},
                },
            },
            handler=lambda ctx, args: list_runners_tool(ctx.gitlab, args),
        ),
        ToolSpec(
            name="gitlab.runners.pause",
            description="Pause/Resume a runner.",
            schema={
                "type": "object",
                "properties": {
                    "runner_id": {"type": "integer"},
                    "paused": {"type": "boolean", "default": True},
                },
                "required": ["runner_id"],
            },
            handler=lambda ctx, args: pause_runner_tool(ctx.gitlab, args),
        ),
        ToolSpec(
            name="knowledge.wiki.list_pages",
            description="List markdown wiki pages for the hlidskjalf project.",
            schema={
                "type": "object",
                "properties": {},
            },
            handler=lambda ctx, args: list_wiki_pages(
                ctx.gitlab, context.settings.gitlab_project_path
            ),
        ),
        ToolSpec(
            name="knowledge.docs.sync_status",
            description="Report the status of doc→wiki synchronization (read-only for now).",
            schema={"type": "object", "properties": {}},
            handler=lambda ctx, args: docs_sync_status(
                list_wiki_pages(ctx.gitlab, context.settings.gitlab_project_path),
                context.settings.knowledge_reference_doc,
            ),
        ),
        ToolSpec(
            name="zitadel.users.list_roles",
            description="List Zitadel project roles for a user (by user_id or email).",
            schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "email": {"type": "string"},
                },
            },
            handler=lambda ctx, args: list_user_roles_tool(ctx, args),
        ),
        ToolSpec(
            name="zitadel.users.assign_roles",
            description="Assign Zitadel project roles to a user.",
            schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "email": {"type": "string"},
                    "role_keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                },
                "required": ["role_keys"],
            },
            handler=lambda ctx, args: assign_user_roles_tool(ctx, args),
        ),
        ToolSpec(
            name="zitadel.service_accounts.create",
            description="Create a Zitadel machine user + PAT and (optionally) assign roles.",
            schema={
                "type": "object",
                "properties": {
                    "user_name": {"type": "string"},
                    "display_name": {"type": "string"},
                    "description": {"type": "string"},
                    "role_keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                },
                "required": ["user_name"],
            },
            handler=lambda ctx, args: create_service_account_tool(ctx, args),
        ),
        ToolSpec(
            name="docker.containers.list",
            description="List Docker containers on the platform host.",
            schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "label": {"type": "string"},
                    "name": {"type": "string"},
                },
            },
            handler=lambda ctx, args: list_containers_tool(ctx, args),
        ),
        ToolSpec(
            name="docker.containers.stats",
            description="Fetch CPU/Memory stats for a container by ID or name.",
            schema={
                "type": "object",
                "properties": {
                    "container_id": {"type": "string"},
                },
                "required": ["container_id"],
            },
            handler=lambda ctx, args: container_stats_tool(ctx, args),
        ),
    ]

    tool_map = {tool.name: tool for tool in tools}
    return tools, tool_map


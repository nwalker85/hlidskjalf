"""
The Norns' Tools — Actions they can take to weave fate

These tools allow the Norns to:
- Observe the Nine Realms (Verðandi's sight)
- Recall what has been (Urðr's memory)
- Shape what will be (Skuld's weaving)
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional, Annotated, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.norns.planner import generate_todo_plan
from src.services.twilio_notifier import get_twilio_notifier
from src.norns.skills import SKILL_TOOLS, get_skills_context
from src.norns.subagent_spawner import SUBAGENT_SPAWNER_TOOLS
from src.norns.self_awareness import SELF_AWARENESS_TOOLS
from src.norns.memory_tools import MEMORY_TOOLS

WORKSPACE_ROOT = Path(os.environ.get("HLIDSKJALF_WORKSPACE", Path(__file__).resolve().parents[3])).resolve()


def _resolve_workspace_path(path: str) -> Path:
    candidate = (WORKSPACE_ROOT / path).resolve()
    if WORKSPACE_ROOT not in candidate.parents and candidate != WORKSPACE_ROOT:
        raise ValueError("Path escapes the workspace boundary")
    return candidate


# =============================================================================
# VERÐANDI'S TOOLS — Observing the Present
# =============================================================================

class PlatformOverviewInput(BaseModel):
    """Input for getting platform overview"""
    include_health: bool = Field(default=True, description="Include health status")


@tool
async def get_platform_overview(include_health: bool = True) -> dict:
    """
    [Verðandi] Observe the current state of all Nine Realms.
    
    Returns an overview of all projects, deployments, and their health status.
    Use this to understand the current state of the platform.
    """
    # This will be injected with the actual session at runtime
    return {
        "status": "This tool requires database session injection",
        "hint": "Use NornsAgent.invoke() with proper context"
    }


@tool
async def list_projects(realm: Optional[str] = None) -> list[dict]:
    """
    [Verðandi] List all projects registered in the platform.
    
    Args:
        realm: Optional realm filter (midgard, alfheim, asgard, etc.)
    
    Returns a list of all projects with their current deployment status.
    """
    return {"status": "requires_injection"}


@tool
async def get_project_details(project_id: str) -> dict:
    """
    [Verðandi] Get detailed information about a specific project.
    
    Args:
        project_id: The ID of the project (e.g., "saaa", "ravenmaskos")
    
    Returns project configuration, port allocations, and deployment history.
    """
    return {"status": "requires_injection", "project_id": project_id}


@tool
async def check_deployment_health(deployment_id: str) -> dict:
    """
    [Verðandi] Check the health of a specific deployment RIGHT NOW.
    
    Performs an immediate health check and returns the results.
    Use this when you need current, real-time health information.
    """
    return {"status": "requires_injection", "deployment_id": deployment_id}


# =============================================================================
# URÐR'S TOOLS — Analyzing the Past
# =============================================================================

@tool
async def analyze_logs(
    project_id: str,
    time_range: str = "1h",
    log_level: str = "error"
) -> dict:
    """
    [Urðr] Analyze logs from the past to understand what has happened.
    
    Args:
        project_id: The project to analyze
        time_range: How far back to look (e.g., "1h", "24h", "7d")
        log_level: Minimum log level to include (debug, info, warn, error)
    
    Returns log analysis with patterns, errors, and insights.
    """
    return {
        "status": "requires_injection",
        "project_id": project_id,
        "time_range": time_range
    }


@tool
async def get_deployment_history(
    project_id: str,
    limit: int = 10
) -> list[dict]:
    """
    [Urðr] Recall the history of deployments for a project.
    
    Returns past deployments, their outcomes, and any issues encountered.
    """
    return {"status": "requires_injection", "project_id": project_id}


@tool
async def get_health_trends(
    deployment_id: str,
    time_range: str = "24h"
) -> dict:
    """
    [Urðr] Analyze health check history to identify trends and patterns.
    
    Returns health metrics over time, identifying degradation patterns.
    """
    return {"status": "requires_injection", "deployment_id": deployment_id}


# =============================================================================
# SKULD'S TOOLS — Shaping the Future
# =============================================================================

@tool
async def allocate_ports(
    project_id: str,
    services: list[dict],
    realm: str = "midgard"
) -> dict:
    """
    [Skuld] Weave new port allocations for a project's services.
    
    Args:
        project_id: The project to allocate ports for
        services: List of services, each with "name" and "type" (http/https/grpc/metrics)
        realm: The realm to allocate in (midgard for dev, alfheim for staging, etc.)
    
    Example services:
        [{"name": "api", "type": "https"}, {"name": "frontend", "type": "https"}]
    
    Returns the allocated ports for each service.
    """
    return {
        "status": "requires_injection",
        "project_id": project_id,
        "services": services,
        "realm": realm
    }


@tool
async def generate_nginx_config(project_id: str) -> str:
    """
    [Skuld] Weave a new nginx configuration for a project.
    
    Generates the nginx server blocks needed to route traffic to the project.
    Returns the configuration as a string.
    """
    return "# Requires injection"


@tool
async def predict_issues(project_id: Optional[str] = None) -> dict:
    """
    [Skuld] Peer into the threads of fate to predict potential issues.
    
    Analyzes current trends and patterns to predict:
    - Potential resource exhaustion
    - Likely failures based on health trends
    - Scaling needs
    
    Args:
        project_id: Optional - focus on a specific project, or None for platform-wide
    """
    return {"status": "requires_injection", "project_id": project_id}


@tool
async def plan_deployment(
    project_id: str,
    target_realm: str,
    version: Optional[str] = None
) -> dict:
    """
    [Skuld] Plan a deployment to a realm.
    
    Creates a deployment plan including:
    - Pre-flight checks
    - Port allocations needed
    - Nginx configuration changes
    - Rollback strategy
    
    Does NOT execute the deployment - just plans it.
    """
    return {
        "status": "requires_injection",
        "project_id": project_id,
        "target_realm": target_realm,
        "version": version
    }


@tool
async def register_project(
    project_id: str,
    name: str,
    subdomain: str,
    description: Optional[str] = None,
    git_repo_url: Optional[str] = None
) -> dict:
    """
    [Skuld] Register a new project in the platform.
    
    Creates a new project entry in Yggdrasil (the project registry).
    
    Args:
        project_id: Unique identifier (lowercase, alphanumeric with hyphens)
        name: Human-readable name
        subdomain: The subdomain for routing (e.g., "myproject" -> *.myproject.ravenhelm.test)
        description: Optional description
        git_repo_url: Optional Git repository URL
    """
    return {
        "status": "requires_injection",
        "project_id": project_id,
        "name": name,
        "subdomain": subdomain
    }


class TwilioMessageInput(BaseModel):
    """Input for dispatching notifications through Twilio"""

    to_number: str = Field(..., description="Destination number in E.164 format (+12025550123)")
    message: str = Field(..., description="Body of the SMS/MMS message")
    media_urls: Optional[list[str]] = Field(
        default=None,
        description="Optional HTTPS URLs for MMS attachments",
    )


@tool("send_twilio_message", args_schema=TwilioMessageInput)
async def send_twilio_message(
    to_number: str,
    message: str,
    media_urls: Optional[list[str]] = None,
) -> dict:
    """
    [Skuld] Dispatch an urgent raven via Twilio SMS/MMS.

    Useful for paging Odin when critical incidents unfold or confirming that
    fate-weaving steps completed successfully.
    """
    notifier = get_twilio_notifier()
    if notifier is None:
        return {
            "status": "disabled",
            "reason": "Twilio credentials or source identifiers were not provided",
        }

    try:
        sid = await asyncio.to_thread(
            notifier.send_message,
            to_number,
            message,
            media_urls,
        )
        return {"status": "sent", "sid": sid}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# =============================================================================
# DEEP AGENT TOOLS — Planning, Filesystem, Subagents
# =============================================================================


class WriteTodosInput(BaseModel):
    """Structured TODO planning request"""

    goal: str = Field(..., description="High level objective to break down")
    context: Optional[str] = Field(
        default=None,
        description="Relevant details, constraints, or prior observations",
    )


@tool("write_todos", args_schema=WriteTodosInput)
async def write_todos(goal: str, context: Optional[str] = None) -> dict:
    """
    Ask Skuld to decompose a goal into actionable TODO items.
    """
    plan = await asyncio.to_thread(generate_todo_plan, goal, context)
    return {"todos": plan}


class WorkspacePathInput(BaseModel):
    path: str = Field(default=".", description="Path relative to the workspace root")


@tool("workspace_list", args_schema=WorkspacePathInput)
async def workspace_list(path: str = ".") -> dict:
    """
    List files and folders rooted at the repository workspace.
    """
    target = _resolve_workspace_path(path)
    entries = []
    for child in sorted(target.iterdir()):
        entries.append(
            {
                "name": child.name,
                "is_dir": child.is_dir(),
                "size": child.stat().st_size,
            }
        )
    return {"path": str(target.relative_to(WORKSPACE_ROOT)), "entries": entries}


class WorkspaceReadInput(BaseModel):
    path: str = Field(..., description="File path relative to workspace root")
    start_line: Optional[int] = Field(
        default=None, description="Optional starting line number (1-indexed)"
    )
    end_line: Optional[int] = Field(
        default=None, description="Optional ending line number (inclusive)"
    )


@tool("workspace_read", args_schema=WorkspaceReadInput)
async def workspace_read(path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> dict:
    """
    Read file contents from the workspace with optional line slicing.
    """
    target = _resolve_workspace_path(path)
    if not target.exists() or not target.is_file():
        return {"error": "File not found"}

    content = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    start = max(start_line - 1, 0) if start_line else 0
    end = end_line if end_line else len(content)
    snippet = "\n".join(content[start:end])
    return {
        "path": str(target.relative_to(WORKSPACE_ROOT)),
        "start_line": start + 1,
        "end_line": end,
        "content": snippet,
    }


class WorkspaceWriteInput(BaseModel):
    path: str = Field(..., description="File path relative to workspace root")
    content: str = Field(..., description="Content to write")
    mode: Literal["overwrite", "append"] = Field(
        default="overwrite",
        description="Overwrite the file or append to the end",
    )


@tool("workspace_write", args_schema=WorkspaceWriteInput)
async def workspace_write(path: str, content: str, mode: Literal["overwrite", "append"] = "overwrite") -> dict:
    """
    Write or append to a workspace file.
    """
    target = _resolve_workspace_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "append" and target.exists():
        target.write_text(target.read_text(encoding="utf-8") + content, encoding="utf-8")
    else:
        target.write_text(content, encoding="utf-8")
    return {
        "path": str(target.relative_to(WORKSPACE_ROOT)),
        "status": "written",
        "mode": mode,
    }


class TerminalCommandInput(BaseModel):
    command: str = Field(..., description="Shell command to execute")
    working_dir: Optional[str] = Field(
        default=None,
        description="Working directory (relative to workspace root)",
    )
    timeout: int = Field(
        default=300,
        description="Command timeout in seconds",
    )


@tool("execute_terminal_command", args_schema=TerminalCommandInput)
async def execute_terminal_command(
    command: str,
    working_dir: Optional[str] = None,
    timeout: int = 300
) -> dict:
    """
    Execute a shell command in the workspace. Use for running docker, git, file operations, etc.
    Returns stdout, stderr, and exit code.
    """
    import subprocess
    
    cwd = WORKSPACE_ROOT
    if working_dir:
        cwd = _resolve_workspace_path(working_dir)
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )
        
        return {
            "command": command,
            "exit_code": process.returncode,
            "stdout": stdout.decode('utf-8', errors='ignore').strip(),
            "stderr": stderr.decode('utf-8', errors='ignore').strip(),
            "success": process.returncode == 0
        }
    except asyncio.TimeoutError:
        return {
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "success": False
        }
    except Exception as e:
        return {
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False
        }


class SubAgentInput(BaseModel):
    goal: str = Field(..., description="The sub-task or investigation to perform")
    context: Optional[str] = Field(
        default=None,
        description="Relevant conversation history or constraints",
    )
    model: Optional[str] = Field(
        default=None,
        description="Override the default model for the specialist",
    )


@tool("spawn_subagent", args_schema=SubAgentInput)
async def spawn_subagent(goal: str, context: Optional[str] = None, model: Optional[str] = None) -> dict:
    """
    Launch a focused specialist agent to go deep on a sub-problem.
    """
    settings = get_settings()
    llm = ChatOpenAI(model=model or settings.NORNS_MODEL, temperature=0.2)
    messages = [
        SystemMessage(
            content=(
                "You are a specialist subagent spawned by the Norns. Produce a concise"
                " report containing findings, risks, and recommended next actions."
            )
        ),
        HumanMessage(content=f"Goal: {goal}\n\nContext:\n{context or 'None'}"),
    ]
    response = await llm.ainvoke(messages)
    return {
        "goal": goal,
        "result": response.content,
    }


# =============================================================================
# ALL TOOLS
# =============================================================================

NORN_TOOLS = [
    # Verðandi - Present
    get_platform_overview,
    list_projects,
    get_project_details,
    check_deployment_health,
    # Urðr - Past
    analyze_logs,
    get_deployment_history,
    get_health_trends,
    # Skuld - Future
    allocate_ports,
    generate_nginx_config,
    predict_issues,
    plan_deployment,
    register_project,
    send_twilio_message,
    write_todos,
    workspace_list,
    workspace_read,
    workspace_write,
    execute_terminal_command,
    spawn_subagent,
    # Skills - Learning and Self-Improvement
    *SKILL_TOOLS,
    # Subagent Spawning - Create new agent types
    *SUBAGENT_SPAWNER_TOOLS,
    # Self-Awareness - Introspection and self-modification
    *SELF_AWARENESS_TOOLS,
    # Memory - Raven Cognitive Architecture
    *MEMORY_TOOLS,
]


"""
The Norns' Tools — Actions they can take to weave fate

These tools allow the Norns to:
- Observe the Nine Realms (Verðandi's sight)
- Recall what has been (Urðr's memory)
- Shape what will be (Skuld's weaving)

All file operations are async to avoid blocking the event loop.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Annotated, Literal

import aiofiles
import aiofiles.os
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

# Known path mappings for host -> container translation
# When running in Docker, the host path /Users/.../hlidskjalf maps to /app
HOST_PATH_PATTERNS = [
    "/Users/nwalker/Development/hlidskjalf",
    "~/Development/hlidskjalf",
]


# =============================================================================
# ASYNC FILE HELPERS
# =============================================================================

async def _path_exists(path: Path) -> bool:
    """Async check if path exists."""
    return await asyncio.to_thread(path.exists)


async def _path_is_file(path: Path) -> bool:
    """Async check if path is a file."""
    return await asyncio.to_thread(path.is_file)


async def _path_is_dir(path: Path) -> bool:
    """Async check if path is a directory."""
    return await asyncio.to_thread(path.is_dir)


async def _list_dir(path: Path) -> list[Path]:
    """Async directory listing."""
    return await asyncio.to_thread(lambda: sorted(list(path.iterdir())))


async def _stat_size(path: Path) -> int:
    """Async get file size."""
    stat = await asyncio.to_thread(path.stat)
    return stat.st_size


async def _read_text(path: Path, encoding: str = "utf-8") -> str:
    """Async file read."""
    async with aiofiles.open(path, mode='r', encoding=encoding, errors='ignore') as f:
        return await f.read()


async def _write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Async file write."""
    async with aiofiles.open(path, mode='w', encoding=encoding) as f:
        await f.write(content)


async def _mkdir(path: Path, parents: bool = False, exist_ok: bool = False) -> None:
    """Async directory creation."""
    await asyncio.to_thread(path.mkdir, parents=parents, exist_ok=exist_ok)


def _resolve_workspace_path(path: str) -> Path:
    """
    Resolve a path to an absolute path within the workspace.
    
    Handles:
    - Relative paths (joined with WORKSPACE_ROOT)
    - Absolute host paths (translated to container paths)
    - Home directory expansion (~)
    """
    # Expand home directory
    if path.startswith("~"):
        path = os.path.expanduser(path)
    
    # Check if this is an absolute host path that needs translation
    for host_pattern in HOST_PATH_PATTERNS:
        expanded_pattern = os.path.expanduser(host_pattern)
        if path.startswith(expanded_pattern):
            # Translate host path to container path
            relative_part = path[len(expanded_pattern):].lstrip("/")
            candidate = (WORKSPACE_ROOT / relative_part).resolve()
            return candidate
        if path == expanded_pattern:
            return WORKSPACE_ROOT
    
    # If it's an absolute path that exists, use it directly
    # (for cases where we're running locally, not in Docker)
    if path.startswith("/"):
        abs_path = Path(path).resolve()
        # Check if it's within or is the workspace root
        try:
            abs_path.relative_to(WORKSPACE_ROOT)
            return abs_path
        except ValueError:
            # Path is outside workspace - check if workspace is inside this path
            try:
                WORKSPACE_ROOT.relative_to(abs_path)
                return abs_path  # Allow parent paths of workspace
            except ValueError:
                pass
            # Path is truly outside - still allow if it exists (for reading system info)
            if abs_path.exists():
                return abs_path
            # Fall through to relative path handling
    
    # Default: treat as relative path
    candidate = (WORKSPACE_ROOT / path).resolve()
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
    
    Handles both relative paths and absolute paths. Host paths like
    /Users/nwalker/Development/hlidskjalf are automatically translated.
    """
    try:
        target = _resolve_workspace_path(path)
        
        if not await _path_exists(target):
            return {
                "error": f"Path does not exist: {path}",
                "hint": "Use '.' for workspace root, or a relative path like 'docs/'",
                "workspace_root": str(WORKSPACE_ROOT),
            }
        
        if not await _path_is_dir(target):
            return {
                "error": f"Path is not a directory: {path}",
                "hint": "Use workspace_read for files",
            }
        
        entries = []
        children = await _list_dir(target)
        for child in children:
            is_dir = await _path_is_dir(child)
            size = await _stat_size(child) if not is_dir else 0
            entries.append(
                {
                    "name": child.name,
                    "is_dir": is_dir,
                    "size": size,
                }
            )
        
        # Try to make path relative, fall back to absolute
        try:
            display_path = str(target.relative_to(WORKSPACE_ROOT))
        except ValueError:
            display_path = str(target)
        
        return {"path": display_path, "entries": entries}
        
    except Exception as e:
        return {
            "error": f"Failed to list directory: {str(e)}",
            "path": path,
            "hint": "Try using a relative path like '.' or 'docs/'",
        }


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
    
    Handles both relative paths and absolute paths. Host paths like
    /Users/nwalker/Development/hlidskjalf are automatically translated.
    """
    try:
        target = _resolve_workspace_path(path)
        
        if not await _path_exists(target):
            return {
                "error": f"File not found: {path}",
                "hint": "Check the path exists. Use workspace_list to browse.",
            }
        
        if not await _path_is_file(target):
            return {
                "error": f"Path is a directory, not a file: {path}",
                "hint": "Use workspace_list for directories",
            }

        file_content = await _read_text(target)
        content = file_content.splitlines()
        start = max(start_line - 1, 0) if start_line else 0
        end = end_line if end_line else len(content)
        snippet = "\n".join(content[start:end])
        
        # Try to make path relative, fall back to absolute
        try:
            display_path = str(target.relative_to(WORKSPACE_ROOT))
        except ValueError:
            display_path = str(target)
        
        return {
            "path": display_path,
            "start_line": start + 1,
            "end_line": end,
            "content": snippet,
            "total_lines": len(content),
        }
        
    except Exception as e:
        return {
            "error": f"Failed to read file: {str(e)}",
            "path": path,
            "hint": "Check file permissions and path validity",
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
    
    Handles both relative paths and absolute paths. Host paths like
    /Users/nwalker/Development/hlidskjalf are automatically translated.
    """
    try:
        target = _resolve_workspace_path(path)
        await _mkdir(target.parent, parents=True, exist_ok=True)
        
        if mode == "append" and await _path_exists(target):
            existing = await _read_text(target)
            await _write_text(target, existing + content)
        else:
            await _write_text(target, content)
        
        # Try to make path relative, fall back to absolute
        try:
            display_path = str(target.relative_to(WORKSPACE_ROOT))
        except ValueError:
            display_path = str(target)
        
        return {
            "path": display_path,
            "status": "written",
            "mode": mode,
            "bytes_written": len(content),
        }
        
    except Exception as e:
        return {
            "error": f"Failed to write file: {str(e)}",
            "path": path,
            "hint": "Check file permissions and path validity",
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
            "stdout": str(stdout.decode('utf-8', errors='ignore')).strip(),
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




# -----------------------------------------------------------------------------
# RUN_BASH_COMMAND - Added by self-modification
# -----------------------------------------------------------------------------

@tool
def run_bash_command(command: str) -> Dict[str, Any]:
    """
    Execute a bash command and return the output, error, and exit code.

    Args:
        command: The bash command to execute.

    Returns:
        A dictionary with keys 'stdout', 'stderr', and 'exit_code'.
    """
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {
        'stdout': result.stdout,
        'stderr': result.stderr,
        'exit_code': result.returncode
    }


# =============================================================================
# WEB SEARCH TOOLS
# =============================================================================

class WebSearchInput(BaseModel):
    query: str = Field(..., description="The search query")
    num_results: int = Field(default=5, description="Number of results to return (max 10)")


@tool("web_search", args_schema=WebSearchInput)
async def web_search(query: str, num_results: int = 5) -> dict:
    """
    Search the web for information. Use this when you need current information,
    documentation, or answers that may not be in your training data.
    
    Examples:
    - "LangGraph StateGraph documentation"
    - "Docker compose healthcheck syntax"
    - "Traefik TLS configuration"
    - "Python 3.13 new features"
    """
    import httpx
    import urllib.parse
    
    num_results = min(num_results, 10)  # Cap at 10
    
    # Try Tavily first if API key is available
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if tavily_key:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": tavily_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": num_results,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for r in data.get("results", [])[:num_results]:
                        results.append({
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "snippet": r.get("content", "")[:500],
                        })
                    return {
                        "query": query,
                        "source": "tavily",
                        "results": results,
                        "answer": data.get("answer", ""),
                    }
        except Exception:
            pass  # Fall through to DuckDuckGo
    
    # Fallback to DuckDuckGo (no API key required)
    try:
        encoded_query = urllib.parse.quote(query)
        async with httpx.AsyncClient(timeout=15.0) as client:
            # DuckDuckGo Instant Answer API
            resp = await client.get(
                f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1",
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                
                # Abstract (main answer)
                if data.get("AbstractText"):
                    results.append({
                        "title": data.get("Heading", "Summary"),
                        "url": data.get("AbstractURL", ""),
                        "snippet": data.get("AbstractText", "")[:500],
                    })
                
                # Related topics
                for topic in data.get("RelatedTopics", [])[:num_results - len(results)]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({
                            "title": topic.get("Text", "")[:100],
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", "")[:500],
                        })
                
                # If no results from instant answer, provide guidance
                if not results:
                    return {
                        "query": query,
                        "source": "duckduckgo",
                        "results": [],
                        "hint": "No instant answers found. Try a more specific query or use fetch_url for direct URL access.",
                    }
                
                return {
                    "query": query,
                    "source": "duckduckgo",
                    "results": results,
                }
    except Exception as e:
        return {
            "error": f"Search failed: {str(e)}",
            "query": query,
            "hint": "Try using fetch_url for direct web requests",
        }
    
    return {
        "error": "Search unavailable",
        "query": query,
        "hint": "No search providers available. Set TAVILY_API_KEY for better results.",
    }


class FetchURLInput(BaseModel):
    url: str = Field(..., description="The URL to fetch")
    extract_text: bool = Field(default=True, description="Extract text content only (no HTML)")


@tool("fetch_url", args_schema=FetchURLInput)
async def fetch_url(url: str, extract_text: bool = True) -> dict:
    """
    Fetch content from a URL. Useful for reading documentation, APIs, or web pages.
    
    Examples:
    - fetch_url("https://docs.python.org/3/whatsnew/3.13.html")
    - fetch_url("https://api.github.com/repos/langchain-ai/langgraph")
    """
    import httpx
    import re
    import html
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Norns/1.0; +https://ravenhelm.test)",
            "Accept": "text/html,application/json,text/plain,*/*",
        }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            content_type = resp.headers.get("Content-Type", "")
            
            if resp.status_code != 200:
                return {
                    "error": f"HTTP {resp.status_code}",
                    "url": url,
                }
            
            # Handle JSON
            if "application/json" in content_type:
                data = resp.json()
                return {
                    "url": url,
                    "content_type": "json",
                    "content": data,
                }
            
            # Handle text/HTML
            text = resp.text
            
            if extract_text and "text/html" in content_type:
                # Basic HTML to text conversion
                # Remove script and style elements
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', ' ', text)
                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text).strip()
                # Decode HTML entities
                text = html.unescape(text)
            
            # Truncate if too long
            if len(text) > 10000:
                text = text[:10000] + "\n\n[... truncated, content too long ...]"
            
            return {
                "url": url,
                "content_type": content_type.split(";")[0],
                "content": text,
                "length": len(text),
            }
                
    except Exception as e:
        return {
            "error": f"Failed to fetch URL: {str(e)}",
            "url": url,
            "hint": "Check if the URL is accessible and correctly formatted",
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
    # Web Search - Seek knowledge from the wider world
    web_search,
    fetch_url,
    # Skills - Learning and Self-Improvement
    *SKILL_TOOLS,
    # Subagent Spawning - Create new agent types
    *SUBAGENT_SPAWNER_TOOLS,
    # Self-Awareness - Introspection and self-modification
    *SELF_AWARENESS_TOOLS,
    # Memory - Raven Cognitive Architecture
    *MEMORY_TOOLS,
    run_bash_command,
]

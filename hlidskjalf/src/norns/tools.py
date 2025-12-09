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


async def _load_port_registry() -> dict:
    """Load the port registry YAML file."""
    import yaml
    registry_path = WORKSPACE_ROOT / "config" / "port_registry.yaml"
    if not await _path_exists(registry_path):
        return {}
    content = await _read_text(registry_path)
    return yaml.safe_load(content) or {}


async def _get_docker_containers() -> list[dict]:
    """Get running Docker containers."""
    import subprocess
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return []
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split('\t')
                containers.append({
                    "name": parts[0] if len(parts) > 0 else "",
                    "status": parts[1] if len(parts) > 1 else "",
                    "ports": parts[2] if len(parts) > 2 else "",
                })
        return containers
    except Exception:
        return []


@tool
async def get_platform_overview(include_health: bool = True) -> dict:
    """
    [Verðandi] Observe the current state of all Nine Realms.
    
    Returns an overview of all projects, deployments, and their health status.
    Use this to understand the current state of the platform.
    """
    registry = await _load_port_registry()
    containers = await _get_docker_containers() if include_health else []
    running_names = {c["name"] for c in containers}
    
    # Build overview from registry
    overview = {
        "workspace": str(WORKSPACE_ROOT),
        "platform_services": [],
        "personal_projects": [],
        "work_projects": [],
        "shared_resources": [],
        "infrastructure": {
            "ports": registry.get("ports", [])[:10],  # First 10 ports
            "ranges": registry.get("ranges", {}),
        }
    }
    
    # Platform services
    for name, config in registry.get("platform", {}).items():
        service = {
            "name": name,
            "domain": config.get("domain", ""),
            "api_port": config.get("api_port"),
            "ui_port": config.get("ui_port"),
            "description": config.get("description", ""),
        }
        if include_health:
            service["running"] = any(name.replace("-", "") in c.lower() or name in c.lower() for c in running_names)
        overview["platform_services"].append(service)
    
    # Personal projects
    for name, config in registry.get("personal", {}).items():
        project = {
            "name": name,
            "realm": config.get("realm", "midgard"),
            "domain": config.get("domain", ""),
            "status": config.get("status", "unknown"),
            "description": config.get("description", ""),
        }
        overview["personal_projects"].append(project)
    
    # Work projects
    for name, config in registry.get("work", {}).items():
        project = {
            "name": name,
            "realm": config.get("realm", "alfheim"),
            "domain": config.get("domain", ""),
            "status": config.get("status", "unknown"),
            "description": config.get("description", ""),
        }
        overview["work_projects"].append(project)
    
    # Shared resources
    for name, config in registry.get("shared", {}).items():
        overview["shared_resources"].append({
            "name": name,
            "type": config.get("type", ""),
            "description": config.get("description", ""),
        })
    
    return overview


@tool
async def list_projects(realm: Optional[str] = None) -> list[dict]:
    """
    [Verðandi] List all projects registered in the platform.
    
    Args:
        realm: Optional realm filter (midgard, alfheim, asgard, jotunheim, etc.)
    
    Returns a list of all projects with their current deployment status.
    """
    registry = await _load_port_registry()
    projects = []
    
    # Collect all projects
    for category in ["platform", "personal", "work", "shared"]:
        for name, config in registry.get(category, {}).items():
            project = {
                "name": name,
                "category": category,
                "realm": config.get("realm", "midgard" if category == "personal" else "alfheim"),
                "domain": config.get("domain", ""),
                "status": config.get("status", "active" if category == "platform" else "unknown"),
                "description": config.get("description", ""),
                "path": config.get("path", ""),
                "api_port": config.get("api_port"),
                "ui_port": config.get("ui_port"),
            }
            
            # Filter by realm if specified
            if realm and project["realm"] != realm:
                continue
                
            projects.append(project)
    
    return projects


@tool
async def get_project_details(project_id: str) -> dict:
    """
    [Verðandi] Get detailed information about a specific project.
    
    Args:
        project_id: The ID of the project (e.g., "hlidskjalf-api", "agentswarm", "jarvis")
    
    Returns project configuration, port allocations, and deployment history.
    """
    registry = await _load_port_registry()
    
    # Search through all categories
    for category in ["platform", "personal", "work", "shared"]:
        projects = registry.get(category, {})
        if project_id in projects:
            config = projects[project_id]
            return {
                "name": project_id,
                "category": category,
                "found": True,
                "path": config.get("path", ""),
                "domain": config.get("domain", ""),
                "domain_aliases": config.get("domain_aliases", []),
                "api_port": config.get("api_port"),
                "ui_port": config.get("ui_port"),
                "realm": config.get("realm", ""),
                "status": config.get("status", ""),
                "description": config.get("description", ""),
                "git_remote": config.get("git_remote", ""),
                "health_endpoint": config.get("health_endpoint", ""),
                "services": config.get("services", []),
                "note": config.get("note", ""),
            }
    
    # Check if it's a partial match
    for category in ["platform", "personal", "work", "shared"]:
        for name, config in registry.get(category, {}).items():
            if project_id.lower() in name.lower():
                return {
                    "name": name,
                    "category": category,
                    "found": True,
                    "partial_match": True,
                    "searched_for": project_id,
                    "path": config.get("path", ""),
                    "domain": config.get("domain", ""),
                    "description": config.get("description", ""),
                }
    
    return {"found": False, "project_id": project_id, "hint": "Try list_projects() to see available projects"}


@tool
async def check_deployment_health(deployment_id: str) -> dict:
    """
    [Verðandi] Check the health of a specific deployment RIGHT NOW.
    
    Performs an immediate health check and returns the results.
    Use this when you need current, real-time health information.
    """
    containers = await _get_docker_containers()
    
    # Find matching container(s)
    matches = []
    for c in containers:
        if deployment_id.lower() in c["name"].lower():
            matches.append({
                "name": c["name"],
                "status": c["status"],
                "ports": c["ports"],
                "healthy": "Up" in c["status"] and "(healthy)" in c["status"].lower() if "health" in c["status"].lower() else "Up" in c["status"],
            })
    
    if not matches:
        return {
            "found": False,
            "deployment_id": deployment_id,
            "hint": "No containers found matching this deployment ID"
        }
    
    return {
        "found": True,
        "deployment_id": deployment_id,
        "containers": matches,
        "all_healthy": all(m["healthy"] for m in matches),
    }


# =============================================================================
# URÐR'S TOOLS — Analyzing the Past
# =============================================================================

def _parse_time_range(time_range: str) -> int:
    """Parse time range string to seconds."""
    import re
    match = re.match(r'^(\d+)([smhd])$', time_range.lower())
    if not match:
        return 3600  # Default 1 hour
    value, unit = int(match.group(1)), match.group(2)
    multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return value * multipliers.get(unit, 3600)


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
    import httpx
    import time
    
    seconds = _parse_time_range(time_range)
    end_time = int(time.time())
    start_time = end_time - seconds
    
    # Build LogQL query - search for container name matching project_id
    level_filter = ""
    if log_level == "error":
        level_filter = '|~ "(?i)(error|err|fatal|panic)"'
    elif log_level == "warn":
        level_filter = '|~ "(?i)(warn|warning|error|err|fatal|panic)"'
    elif log_level == "info":
        level_filter = '|~ "(?i)(info|warn|warning|error|err|fatal|panic)"'
    
    query = f'{{container_name=~".*{project_id}.*"}} {level_filter}'
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "http://loki:3100/loki/api/v1/query_range",
                params={
                    "query": query,
                    "start": start_time * 1_000_000_000,  # nanoseconds
                    "end": end_time * 1_000_000_000,
                    "limit": 100,
                },
            )
            
            if resp.status_code != 200:
                return {
                    "error": f"Loki query failed: {resp.status_code}",
                    "project_id": project_id,
                    "fallback": "Loki may not be running or accessible",
                }
            
            data = resp.json()
            results = data.get("data", {}).get("result", [])
            
            # Extract log lines
            log_entries = []
            for stream in results:
                labels = stream.get("stream", {})
                for timestamp, line in stream.get("values", []):
                    log_entries.append({
                        "timestamp": timestamp,
                        "container": labels.get("container_name", "unknown"),
                        "line": line[:500],  # Truncate long lines
                    })
            
            # Simple pattern analysis
            error_count = sum(1 for e in log_entries if any(x in e["line"].lower() for x in ["error", "err", "fatal"]))
            warn_count = sum(1 for e in log_entries if "warn" in e["line"].lower())
            
            return {
                "project_id": project_id,
                "time_range": time_range,
                "log_level": log_level,
                "total_entries": len(log_entries),
                "error_count": error_count,
                "warning_count": warn_count,
                "recent_logs": log_entries[:20],  # Last 20 entries
                "analysis": {
                    "has_errors": error_count > 0,
                    "error_rate": f"{(error_count / len(log_entries) * 100):.1f}%" if log_entries else "0%",
                },
            }
            
    except Exception as e:
        return {
            "error": f"Failed to query logs: {str(e)}",
            "project_id": project_id,
            "hint": "Loki may not be running. Check docker logs for loki service.",
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
    import subprocess
    
    # Get Docker events for the project
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "docker", "events", "--since", "168h", "--until", "0s",
                "--filter", f"container={project_id}",
                "--filter", "event=start",
                "--filter", "event=stop",
                "--filter", "event=die",
                "--format", "{{.Time}} {{.Action}} {{.Actor.Attributes.name}}"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        events = []
        for line in result.stdout.strip().split('\n')[:limit]:
            if line:
                parts = line.split(' ', 2)
                if len(parts) >= 3:
                    events.append({
                        "timestamp": parts[0],
                        "action": parts[1],
                        "container": parts[2],
                    })
        
        if events:
            return {
                "project_id": project_id,
                "events": events,
                "total": len(events),
            }
            
    except Exception:
        pass
    
    # Fallback: Just show current container state
    containers = await _get_docker_containers()
    matching = [c for c in containers if project_id.lower() in c["name"].lower()]
    
    return {
        "project_id": project_id,
        "current_state": matching,
        "history": "Docker events not available - showing current state only",
    }


@tool
async def get_health_trends(
    deployment_id: str,
    time_range: str = "24h"
) -> dict:
    """
    [Urðr] Analyze health check history to identify trends and patterns.
    
    Returns health metrics over time, identifying degradation patterns.
    """
    import httpx
    
    seconds = _parse_time_range(time_range)
    step = max(seconds // 100, 60)  # At most 100 data points
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Query container CPU usage
            cpu_resp = await client.get(
                "http://prometheus:9090/api/v1/query_range",
                params={
                    "query": f'rate(container_cpu_usage_seconds_total{{name=~".*{deployment_id}.*"}}[5m])',
                    "start": f"-{time_range}",
                    "end": "now",
                    "step": f"{step}s",
                },
            )
            
            # Query container memory usage
            mem_resp = await client.get(
                "http://prometheus:9090/api/v1/query_range",
                params={
                    "query": f'container_memory_usage_bytes{{name=~".*{deployment_id}.*"}}',
                    "start": f"-{time_range}",
                    "end": "now",
                    "step": f"{step}s",
                },
            )
            
            trends = {
                "deployment_id": deployment_id,
                "time_range": time_range,
                "metrics": {},
            }
            
            if cpu_resp.status_code == 200:
                cpu_data = cpu_resp.json().get("data", {}).get("result", [])
                if cpu_data:
                    values = [float(v[1]) for v in cpu_data[0].get("values", []) if v[1] != "NaN"]
                    if values:
                        trends["metrics"]["cpu"] = {
                            "avg": f"{sum(values) / len(values) * 100:.2f}%",
                            "max": f"{max(values) * 100:.2f}%",
                            "min": f"{min(values) * 100:.2f}%",
                            "trend": "increasing" if values[-1] > values[0] else "stable" if abs(values[-1] - values[0]) < 0.01 else "decreasing",
                        }
            
            if mem_resp.status_code == 200:
                mem_data = mem_resp.json().get("data", {}).get("result", [])
                if mem_data:
                    values = [float(v[1]) for v in mem_data[0].get("values", []) if v[1] != "NaN"]
                    if values:
                        trends["metrics"]["memory"] = {
                            "avg": f"{sum(values) / len(values) / 1024 / 1024:.1f} MB",
                            "max": f"{max(values) / 1024 / 1024:.1f} MB",
                            "min": f"{min(values) / 1024 / 1024:.1f} MB",
                            "trend": "increasing" if values[-1] > values[0] * 1.1 else "stable" if abs(values[-1] - values[0]) / max(values[0], 1) < 0.1 else "decreasing",
                        }
            
            if not trends["metrics"]:
                trends["note"] = "No metrics found. Prometheus may not be scraping this deployment."
            
            return trends
            
    except Exception as e:
        return {
            "error": f"Failed to query metrics: {str(e)}",
            "deployment_id": deployment_id,
            "hint": "Prometheus may not be running or accessible at prometheus:9090",
        }


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
    import yaml
    
    registry = await _load_port_registry()
    if not registry:
        return {"error": "Could not load port registry"}
    
    # Determine which range to use
    realm_to_range = {
        "midgard": "personal_api",
        "alfheim": "work_api",
        "jotunheim": "sandbox_api",
    }
    range_name = realm_to_range.get(realm, "sandbox_api")
    
    # Get current next_available ports
    next_available = registry.get("next_available", {})
    api_port = next_available.get(range_name, 8300)
    ui_port = next_available.get(f"{range_name.replace('_api', '_ui')}", 3300)
    
    # Allocate ports
    allocations = []
    for svc in services:
        svc_name = svc.get("name", "service")
        svc_type = svc.get("type", "http")
        
        if svc_type in ["frontend", "ui"]:
            allocations.append({
                "service": svc_name,
                "port": ui_port,
                "type": "ui",
            })
            ui_port += 1
        else:
            allocations.append({
                "service": svc_name,
                "port": api_port,
                "type": "api",
            })
            api_port += 1
    
    # Update next_available (but don't write yet - just propose)
    return {
        "project_id": project_id,
        "realm": realm,
        "allocations": allocations,
        "proposed_update": {
            range_name: api_port,
            f"{range_name.replace('_api', '_ui')}": ui_port,
        },
        "note": "Ports allocated but not persisted. Use register_project to save.",
    }


@tool
async def generate_nginx_config(project_id: str) -> str:
    """
    [Skuld] Weave a new nginx configuration for a project.
    
    Generates the nginx server blocks needed to route traffic to the project.
    Returns the configuration as a string.
    """
    # Get project details
    project = await get_project_details.ainvoke({"project_id": project_id})
    
    if not project.get("found"):
        return f"# Error: Project '{project_id}' not found in registry"
    
    domain = project.get("domain", f"{project_id}.ravenhelm.test")
    api_port = project.get("api_port", 8000)
    ui_port = project.get("ui_port")
    
    config = f"""# Auto-generated nginx configuration for {project_id}
# Generated by Norns [Skuld]

upstream {project_id}_api {{
    server 127.0.0.1:{api_port};
}}

server {{
    listen 443 ssl http2;
    server_name {domain};

    ssl_certificate /etc/nginx/certs/ravenhelm.test.crt;
    ssl_certificate_key /etc/nginx/certs/ravenhelm.test.key;

    location / {{
        proxy_pass http://{project_id}_api;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""
    
    if ui_port:
        config += f"""
upstream {project_id}_ui {{
    server 127.0.0.1:{ui_port};
}}

server {{
    listen 443 ssl http2;
    server_name app.{domain};

    ssl_certificate /etc/nginx/certs/ravenhelm.test.crt;
    ssl_certificate_key /etc/nginx/certs/ravenhelm.test.key;

    location / {{
        proxy_pass http://{project_id}_ui;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
}}
"""
    
    return config


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
    import httpx
    
    predictions = {
        "project_id": project_id or "platform-wide",
        "predictions": [],
        "risk_level": "low",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check disk space
            disk_resp = await client.get(
                "http://prometheus:9090/api/v1/query",
                params={"query": '(node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100'},
            )
            
            if disk_resp.status_code == 200:
                disk_data = disk_resp.json().get("data", {}).get("result", [])
                for result in disk_data:
                    pct_free = float(result.get("value", [0, 100])[1])
                    if pct_free < 20:
                        predictions["predictions"].append({
                            "type": "disk_space",
                            "severity": "high" if pct_free < 10 else "medium",
                            "message": f"Disk space low: {pct_free:.1f}% free",
                            "recommendation": "Clean up old Docker images and logs",
                        })
                        predictions["risk_level"] = "high" if pct_free < 10 else "medium"
            
            # Check memory pressure
            mem_resp = await client.get(
                "http://prometheus:9090/api/v1/query",
                params={"query": '(node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100'},
            )
            
            if mem_resp.status_code == 200:
                mem_data = mem_resp.json().get("data", {}).get("result", [])
                for result in mem_data:
                    pct_free = float(result.get("value", [0, 100])[1])
                    if pct_free < 20:
                        predictions["predictions"].append({
                            "type": "memory",
                            "severity": "high" if pct_free < 10 else "medium",
                            "message": f"Memory pressure: {pct_free:.1f}% available",
                            "recommendation": "Consider stopping unused containers or adding swap",
                        })
                        if pct_free < 10:
                            predictions["risk_level"] = "high"
                        elif predictions["risk_level"] != "high":
                            predictions["risk_level"] = "medium"
            
            # Check container restart counts
            if project_id:
                query = f'changes(container_start_time_seconds{{name=~".*{project_id}.*"}}[1h])'
            else:
                query = 'changes(container_start_time_seconds[1h]) > 3'
            
            restart_resp = await client.get(
                "http://prometheus:9090/api/v1/query",
                params={"query": query},
            )
            
            if restart_resp.status_code == 200:
                restart_data = restart_resp.json().get("data", {}).get("result", [])
                for result in restart_data:
                    container = result.get("metric", {}).get("name", "unknown")
                    restarts = int(float(result.get("value", [0, 0])[1]))
                    if restarts > 3:
                        predictions["predictions"].append({
                            "type": "stability",
                            "severity": "high" if restarts > 10 else "medium",
                            "message": f"Container '{container}' restarted {restarts} times in last hour",
                            "recommendation": "Check container logs for crash reasons",
                        })
            
            if not predictions["predictions"]:
                predictions["predictions"].append({
                    "type": "all_clear",
                    "severity": "info",
                    "message": "No immediate issues detected",
                    "recommendation": "Continue monitoring",
                })
            
            return predictions
            
    except Exception as e:
        return {
            "error": f"Prediction analysis failed: {str(e)}",
            "hint": "Prometheus may not be accessible",
            "fallback_prediction": {
                "type": "unknown",
                "severity": "info",
                "message": "Unable to analyze metrics - recommend manual health checks",
            },
        }


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
    # Get current project state
    project = await get_project_details.ainvoke({"project_id": project_id})
    current_health = await check_deployment_health.ainvoke({"deployment_id": project_id})
    
    plan = {
        "project_id": project_id,
        "target_realm": target_realm,
        "version": version or "latest",
        "timestamp": asyncio.get_event_loop().time(),
        "steps": [],
        "pre_flight_checks": [],
        "rollback_strategy": [],
    }
    
    # Pre-flight checks
    if project.get("found"):
        plan["pre_flight_checks"].append({
            "check": "project_exists",
            "status": "passed",
            "details": f"Project registered at {project.get('domain')}",
        })
    else:
        plan["pre_flight_checks"].append({
            "check": "project_exists",
            "status": "failed",
            "details": "Project not found in registry - needs registration first",
        })
        plan["steps"].append({
            "order": 1,
            "action": "register_project",
            "description": f"Register {project_id} in the platform",
        })
    
    if current_health.get("found"):
        plan["pre_flight_checks"].append({
            "check": "current_deployment",
            "status": "passed" if current_health.get("all_healthy") else "warning",
            "details": f"Current deployment: {len(current_health.get('containers', []))} containers",
        })
        plan["rollback_strategy"].append({
            "step": 1,
            "action": "docker rollback",
            "command": f"docker-compose -p {project_id} up -d --force-recreate",
        })
    
    # Deployment steps
    step_num = len(plan["steps"]) + 1
    plan["steps"].extend([
        {
            "order": step_num,
            "action": "pull_images",
            "description": f"Pull Docker images for version {version or 'latest'}",
            "command": f"docker-compose -p {project_id} pull",
        },
        {
            "order": step_num + 1,
            "action": "stop_current",
            "description": "Stop current deployment gracefully",
            "command": f"docker-compose -p {project_id} stop",
        },
        {
            "order": step_num + 2,
            "action": "deploy_new",
            "description": f"Deploy to {target_realm}",
            "command": f"docker-compose -p {project_id} up -d",
        },
        {
            "order": step_num + 3,
            "action": "health_check",
            "description": "Verify deployment health",
            "tool": "check_deployment_health",
        },
    ])
    
    return plan


@tool
async def register_project(
    project_id: str,
    name: str,
    subdomain: str,
    description: Optional[str] = None,
    git_repo_url: Optional[str] = None,
    category: str = "work",
    realm: str = "alfheim"
) -> dict:
    """
    [Skuld] Register a new project in the platform.
    
    Creates a new project entry in Yggdrasil (the project registry).
    
    Args:
        project_id: Unique identifier (lowercase, alphanumeric with hyphens)
        name: Human-readable name
        subdomain: The subdomain for routing (e.g., "myproject" -> myproject.ravenhelm.test)
        description: Optional description
        git_repo_url: Optional Git repository URL
        category: One of "personal", "work", "shared" (default: "work")
        realm: The realm (midgard, alfheim, jotunheim) (default: "alfheim")
    """
    import yaml
    import re
    
    # Validate project_id
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', project_id):
        return {
            "error": "Invalid project_id",
            "hint": "Use lowercase alphanumeric with hyphens, e.g., 'my-project'",
        }
    
    registry = await _load_port_registry()
    if not registry:
        return {"error": "Could not load port registry"}
    
    # Check if project already exists
    for cat in ["platform", "personal", "work", "shared"]:
        if project_id in registry.get(cat, {}):
            return {
                "error": "Project already exists",
                "existing_category": cat,
                "hint": "Use a different project_id or update the existing project",
            }
    
    # Allocate ports
    allocation = await allocate_ports.ainvoke({
        "project_id": project_id,
        "services": [{"name": "api", "type": "http"}, {"name": "ui", "type": "frontend"}],
        "realm": realm,
    })
    
    if "error" in allocation:
        return allocation
    
    # Get allocated ports
    api_port = None
    ui_port = None
    for alloc in allocation.get("allocations", []):
        if alloc["type"] == "api":
            api_port = alloc["port"]
        elif alloc["type"] == "ui":
            ui_port = alloc["port"]
    
    # Create project entry
    project_entry = {
        "path": f"~/Development/{category}/{project_id}",
        "api_port": api_port,
        "ui_port": ui_port,
        "domain": f"{subdomain}.ravenhelm.test",
        "realm": realm,
        "status": "registered",
        "description": description or f"{name} project",
    }
    
    if git_repo_url:
        project_entry["git_remote"] = git_repo_url
    
    # Add to registry
    if category not in registry:
        registry[category] = {}
    registry[category][project_id] = project_entry
    
    # Update next_available
    if "next_available" not in registry:
        registry["next_available"] = {}
    registry["next_available"].update(allocation.get("proposed_update", {}))
    
    # Write back to file
    registry_path = WORKSPACE_ROOT / "config" / "port_registry.yaml"
    try:
        content = yaml.dump(registry, default_flow_style=False, sort_keys=False)
        await _write_text(registry_path, content)
        
        return {
            "success": True,
            "project_id": project_id,
            "domain": project_entry["domain"],
            "api_port": api_port,
            "ui_port": ui_port,
            "category": category,
            "realm": realm,
            "next_steps": [
                f"Create project at {project_entry['path']}",
                "Add docker-compose.yml",
                "Run: docker-compose up -d",
            ],
        }
        
    except Exception as e:
        return {
            "error": f"Failed to write registry: {str(e)}",
            "project_entry": project_entry,
            "hint": "Project config prepared but not saved",
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

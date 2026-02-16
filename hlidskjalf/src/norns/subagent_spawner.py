"""
Subagent Spawner - Tools for creating new subagent types

This module enables the Norns to dynamically create, deploy, and register
new specialized subagent types as Docker containers.

All file operations are async to avoid blocking the event loop.
"""

import os
import re
import yaml
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional
from langchain_core.tools import tool
import aiofiles


# =============================================================================
# ASYNC FILE HELPERS
# =============================================================================

async def _path_exists(path: Path) -> bool:
    """Async check if path exists."""
    return await asyncio.to_thread(path.exists)


async def _read_text(path: Path) -> str:
    """Async file read."""
    async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
        return await f.read()


async def _write_text(path: Path, content: str) -> None:
    """Async file write."""
    async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
        await f.write(content)


async def _mkdir(path: Path, parents: bool = False, exist_ok: bool = False) -> None:
    """Async directory creation."""
    await asyncio.to_thread(path.mkdir, parents=parents, exist_ok=exist_ok)


async def _rmtree(path: Path) -> None:
    """Async recursive directory removal."""
    import shutil
    await asyncio.to_thread(shutil.rmtree, path)


async def _run_command(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> tuple[int, str, str]:
    """Async subprocess execution."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )
        return process.returncode or 0, stdout.decode('utf-8', errors='ignore'), stderr.decode('utf-8', errors='ignore')
    except asyncio.TimeoutError:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


# =============================================================================
# Paths
# =============================================================================

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
AGENTS_DIR = WORKSPACE_ROOT / "hlidskjalf" / "src" / "agents"
CONFIG_DIR = WORKSPACE_ROOT / "config"
DOCKER_COMPOSE_PATH = WORKSPACE_ROOT / "docker-compose.yml"


def to_snake_case(name: str) -> str:
    """Convert kebab-case to snake_case."""
    return name.replace("-", "_")


def to_pascal_case(name: str) -> str:
    """Convert kebab-case to PascalCase."""
    return "".join(word.capitalize() for word in name.split("-"))


def to_upper_snake(name: str) -> str:
    """Convert kebab-case to UPPER_SNAKE_CASE."""
    return name.replace("-", "_").upper()


async def get_next_available_port(base_port: int = 8100) -> int:
    """Find the next available port in the agent range."""
    port_registry = CONFIG_DIR / "port_registry.yaml"
    
    if await _path_exists(port_registry):
        content = await _read_text(port_registry)
        registry = yaml.safe_load(content) or {}
        
        agents = registry.get("agents", {})
        used_ports = [a.get("port", 0) for a in agents.values() if isinstance(a, dict)]
        if used_ports:
            return max(used_ports) + 1
    
    return base_port


async def ensure_registries_exist():
    """Create registry files if they don't exist."""
    await _mkdir(CONFIG_DIR, parents=True, exist_ok=True)
    
    port_registry = CONFIG_DIR / "port_registry.yaml"
    if not await _path_exists(port_registry):
        await _write_text(port_registry, yaml.dump({
            "version": "1.0.0",
            "description": "Ravenhelm Port Registry",
            "agents": {},
            "services": {},
        }))
    
    agent_registry = CONFIG_DIR / "agent_registry.yaml"
    if not await _path_exists(agent_registry):
        await _write_text(agent_registry, yaml.dump({
            "version": "1.0.0",
            "description": "Ravenhelm Agent Registry",
            "agents": {},
        }))


# =============================================================================
# Agent Code Generation Templates
# =============================================================================

INIT_TEMPLATE = '''"""
{agent_title} - {description}
Auto-generated subagent type by Norns.
"""

from .agent import {agent_class}, create_{snake_name}_graph, {upper_name}_GRAPH
from .tools import {upper_name}_TOOLS

__all__ = ["{agent_class}", "create_{snake_name}_graph", "{upper_name}_GRAPH", "{upper_name}_TOOLS"]
'''

AGENT_TEMPLATE = '''"""
{agent_title} Agent Implementation
"""

from typing import Annotated, TypedDict, Literal
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END, add_messages
from langgraph.prebuilt import ToolNode

from .tools import {upper_name}_TOOLS


class {agent_class}State(TypedDict):
    """State for {agent_title} agent."""
    messages: Annotated[list[BaseMessage], add_messages]
    context: dict


SYSTEM_PROMPT = """{description}

You are a specialized subagent in the Ravenhelm platform, created by the Norns.
Execute tasks delegated to you efficiently and report results clearly.

Your capabilities:
{capabilities}

When you complete a task, provide a clear summary of what was done.
"""


def create_{snake_name}_graph(for_api: bool = False):
    """Create the {agent_title} agent graph."""
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="{model}", temperature=0).bind_tools({upper_name}_TOOLS)
    
    def agent_node(state: {agent_class}State) -> dict:
        messages = state["messages"]
        
        # Inject system prompt if not present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
        
        response = llm.invoke(messages)
        return {{"messages": [response]}}
    
    def should_continue(state: {agent_class}State) -> Literal["tools", "__end__"]:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return END
    
    workflow = StateGraph({agent_class}State)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode({upper_name}_TOOLS))
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {{"tools": "tools", END: END}})
    workflow.add_edge("tools", "agent")
    
    if for_api:
        return workflow.compile()
    
    from langgraph.checkpoint.memory import MemorySaver
    return workflow.compile(checkpointer=MemorySaver())


# Export for LangGraph API
{upper_name}_GRAPH = create_{snake_name}_graph(for_api=True)


class {agent_class}:
    """Wrapper class for {agent_title} agent."""
    
    def __init__(self):
        self.graph = create_{snake_name}_graph()
    
    def invoke(self, message: str, thread_id: str = "default") -> str:
        from langchain_core.messages import HumanMessage
        
        result = self.graph.invoke(
            {{"messages": [HumanMessage(content=message)], "context": {{}}}},
            config={{"configurable": {{"thread_id": thread_id}}}}
        )
        
        return result["messages"][-1].content
'''

TOOLS_TEMPLATE = '''"""
Tools for {agent_title} agent.
"""

from langchain_core.tools import tool


# =============================================================================
# {agent_title} Tools
# =============================================================================

@tool
async def agent_status() -> str:
    """Report the current status of this agent."""
    return "{agent_title} agent is operational and ready for tasks."


{custom_tools}


# =============================================================================
# Tool Collection
# =============================================================================

{upper_name}_TOOLS = [
    agent_status,
{tool_list}]
'''

DOCKERFILE_TEMPLATE = '''# {agent_title} Subagent
# Auto-generated by Norns

FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \\
    langchain>=0.3.0 \\
    langchain-openai>=0.2.0 \\
    langchain-anthropic>=0.2.0 \\
    langgraph>=0.2.0 \\
    "langgraph-cli[inmem]"

# Copy agent code
COPY . /app/{snake_name}/

# Create langgraph config
RUN echo '{{ \\
  "python_version": "3.13", \\
  "dependencies": ["."], \\
  "graphs": {{ \\
    "{kebab_name}": "./{snake_name}/agent.py:{upper_name}_GRAPH" \\
  }} \\
}}' > /app/langgraph.json

ENV PYTHONPATH=/app

EXPOSE {port}

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \\
    CMD curl -f http://localhost:{port}/info || exit 1

CMD ["langgraph", "dev", "--host", "0.0.0.0", "--port", "{port}", "--no-browser"]
'''

LANGGRAPH_JSON_TEMPLATE = '''{{
  "python_version": "3.13",
  "dependencies": ["."],
  "graphs": {{
    "{kebab_name}": "./{snake_name}/agent.py:{upper_name}_GRAPH"
  }}
}}
'''


# =============================================================================
# LangChain Tools for Agent Creation
# =============================================================================

@tool
async def spawn_subagent_type(
    name: str,
    description: str,
    model: str = "gpt-4o-mini",
    skills: str = "",
    custom_tools_code: str = "",
    auto_deploy: bool = True
) -> str:
    """Create a new specialized subagent type with its own Docker container.
    
    This creates:
    1. Agent Python module with LangGraph implementation
    2. Dockerfile for containerization
    3. Updates port and agent registries
    4. Optionally builds and deploys the container
    
    Args:
        name: Agent name in kebab-case (e.g., 'security-scanner')
        description: What this agent does
        model: LLM model to use (default: gpt-4o-mini)
        skills: Comma-separated skill names this agent should use
        custom_tools_code: Python code defining custom @tool functions
        auto_deploy: Whether to build and deploy immediately (default: True)
    
    Returns:
        Status message with details about the created agent
    """
    # Validate name
    if not re.match(r'^[a-z][a-z0-9-]*$', name):
        return f"Invalid agent name '{name}'. Use kebab-case (e.g., 'my-agent-name')"
    
    # Derived names
    snake_name = to_snake_case(name)
    pascal_name = to_pascal_case(name)
    upper_name = to_upper_snake(name)
    agent_title = " ".join(word.capitalize() for word in name.split("-"))
    
    # Ensure directories exist
    agent_dir = AGENTS_DIR / name
    if await _path_exists(agent_dir):
        return f"Agent '{name}' already exists at {agent_dir}"
    
    await _mkdir(agent_dir, parents=True)
    await ensure_registries_exist()
    
    # Allocate port
    port = await get_next_available_port()
    
    # Parse skills
    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
    capabilities = "\n".join(f"- {s}" for s in skill_list) if skill_list else "- General task execution"
    
    # Parse custom tools
    tool_names = re.findall(r'@tool\s+(?:async\s+)?def\s+(\w+)', custom_tools_code) if custom_tools_code else []
    tool_list = "    " + ",\n    ".join(tool_names) + "," if tool_names else ""
    
    # Generate files
    init_content = INIT_TEMPLATE.format(
        agent_title=agent_title,
        description=description,
        agent_class=pascal_name + "Agent",
        snake_name=snake_name,
        upper_name=upper_name,
    )
    
    agent_content = AGENT_TEMPLATE.format(
        agent_title=agent_title,
        description=description,
        agent_class=pascal_name + "Agent",
        snake_name=snake_name,
        upper_name=upper_name,
        model=model,
        capabilities=capabilities,
    )
    
    tools_content = TOOLS_TEMPLATE.format(
        agent_title=agent_title,
        upper_name=upper_name,
        custom_tools=custom_tools_code or "# Add custom tools here",
        tool_list=tool_list,
    )
    
    dockerfile_content = DOCKERFILE_TEMPLATE.format(
        agent_title=agent_title,
        snake_name=snake_name,
        kebab_name=name,
        upper_name=upper_name,
        port=port,
    )
    
    langgraph_json = LANGGRAPH_JSON_TEMPLATE.format(
        kebab_name=name,
        snake_name=snake_name,
        upper_name=upper_name,
    )
    
    # Write files
    await _write_text(agent_dir / "__init__.py", init_content)
    await _write_text(agent_dir / "agent.py", agent_content)
    await _write_text(agent_dir / "tools.py", tools_content)
    await _write_text(agent_dir / "Dockerfile", dockerfile_content)
    await _write_text(agent_dir / "langgraph.json", langgraph_json)
    
    # Update port registry
    port_registry_path = CONFIG_DIR / "port_registry.yaml"
    port_content = await _read_text(port_registry_path)
    port_registry = yaml.safe_load(port_content) or {}
    
    if "agents" not in port_registry:
        port_registry["agents"] = {}
    
    port_registry["agents"][name] = {
        "port": port,
        "protocol": "http",
        "health_endpoint": "/info",
        "description": description,
    }
    
    await _write_text(port_registry_path, yaml.dump(port_registry, default_flow_style=False, sort_keys=False))
    
    # Update agent registry
    agent_registry_path = CONFIG_DIR / "agent_registry.yaml"
    agent_content = await _read_text(agent_registry_path)
    agent_registry = yaml.safe_load(agent_content) or {}
    
    if "agents" not in agent_registry:
        agent_registry["agents"] = {}
    
    agent_registry["agents"][name] = {
        "name": agent_title,
        "class": f"{pascal_name}Agent",
        "description": description,
        "version": "1.0.0",
        "model": model,
        "port": port,
        "status": "created",
        "skills": skill_list,
        "tools": tool_names or ["agent_status"],
        "container": {
            "image": f"ravenhelm/{name}:latest",
            "network": "platform_net",
            "restart_policy": "unless-stopped",
        },
        "created_at": datetime.now().isoformat(),
        "created_by": "norns",
    }
    
    await _write_text(agent_registry_path, yaml.dump(agent_registry, default_flow_style=False, sort_keys=False))
    
    result = [
        f"✓ Subagent type '{name}' created successfully!",
        "",
        f"**Location:** {agent_dir}",
        f"**Port:** {port}",
        f"**Model:** {model}",
        f"**Skills:** {', '.join(skill_list) if skill_list else 'none'}",
        f"**Tools:** {', '.join(tool_names) if tool_names else 'agent_status'}",
        "",
        "**Files created:**",
        f"  - {agent_dir}/__init__.py",
        f"  - {agent_dir}/agent.py",
        f"  - {agent_dir}/tools.py",
        f"  - {agent_dir}/Dockerfile",
        f"  - {agent_dir}/langgraph.json",
        "",
        "**Registries updated:**",
        f"  - {port_registry_path}",
        f"  - {agent_registry_path}",
    ]
    
    if auto_deploy:
        # Build Docker image
        result.append("")
        result.append("**Building Docker image...**")
        
        returncode, stdout, stderr = await _run_command(
            ["docker", "build", "-t", f"ravenhelm/{name}:latest", "."],
            cwd=agent_dir,
            timeout=300
        )
        
        if returncode == 0:
            result.append(f"  ✓ Image ravenhelm/{name}:latest built")
            
            # Deploy container
            result.append("")
            result.append("**Deploying container...**")
            
            returncode, stdout, stderr = await _run_command([
                "docker", "run", "-d",
                "--name", f"ravenhelm-{name}",
                "--network", "platform_net",
                "-p", f"{port}:{port}",
                "-e", f"OPENAI_API_KEY={os.environ.get('OPENAI_API_KEY', '')}",
                "-e", f"ANTHROPIC_API_KEY={os.environ.get('ANTHROPIC_API_KEY', '')}",
                "--restart", "unless-stopped",
                "--label", "ravenhelm.project=hlidskjalf",
                "--label", f"ravenhelm.service={name}",
                "--label", "ravenhelm.workload=subagent",
                f"ravenhelm/{name}:latest"
            ], timeout=60)
            
            if returncode == 0:
                result.append(f"  ✓ Container ravenhelm-{name} running on port {port}")
                
                # Update status in registry
                agent_registry["agents"][name]["status"] = "running"
                await _write_text(agent_registry_path, yaml.dump(agent_registry, default_flow_style=False, sort_keys=False))
            else:
                result.append(f"  ✗ Deploy failed: {stderr}")
        else:
            result.append(f"  ✗ Build failed: {stderr[:500]}")
    else:
        result.append("")
        result.append("**To deploy manually:**")
        result.append(f"  cd {agent_dir}")
        result.append(f"  docker build -t ravenhelm/{name}:latest .")
        result.append(f"  docker run -d --name ravenhelm-{name} -p {port}:{port} ravenhelm/{name}:latest")
    
    return "\n".join(result)


@tool
async def list_subagent_types() -> str:
    """List all registered subagent types and their status.
    
    Returns information from the agent registry including:
    - Agent name and description
    - Port allocation
    - Current status (created, running, stopped)
    - Associated skills and tools
    """
    agent_registry_path = CONFIG_DIR / "agent_registry.yaml"
    
    if not await _path_exists(agent_registry_path):
        return "No agent registry found. No subagent types have been created yet."
    
    content = await _read_text(agent_registry_path)
    registry = yaml.safe_load(content) or {}
    
    agents = registry.get("agents", {})
    
    if not agents:
        return "No subagent types registered yet. Use spawn_subagent_type to create one."
    
    lines = ["# Registered Subagent Types", ""]
    
    for name, info in agents.items():
        status_emoji = {"running": "🟢", "created": "🟡", "stopped": "🔴"}.get(info.get("status", "unknown"), "⚪")
        
        lines.append(f"## {info.get('name', name)} ({name})")
        lines.append(f"**Status:** {status_emoji} {info.get('status', 'unknown')}")
        lines.append(f"**Port:** {info.get('port', 'N/A')}")
        lines.append(f"**Model:** {info.get('model', 'N/A')}")
        lines.append(f"**Description:** {info.get('description', 'No description')}")
        
        skills = info.get("skills", [])
        lines.append(f"**Skills:** {', '.join(skills) if skills else 'none'}")
        
        tools = info.get("tools", [])
        lines.append(f"**Tools:** {', '.join(tools) if tools else 'none'}")
        
        lines.append(f"**Created:** {info.get('created_at', 'unknown')}")
        lines.append("")
    
    return "\n".join(lines)


@tool
async def get_subagent_status(name: str) -> str:
    """Get the current status of a specific subagent type.
    
    Args:
        name: The kebab-case name of the subagent type
    
    Returns:
        Detailed status including container health
    """
    agent_registry_path = CONFIG_DIR / "agent_registry.yaml"
    
    if not await _path_exists(agent_registry_path):
        return f"Agent registry not found."
    
    content = await _read_text(agent_registry_path)
    registry = yaml.safe_load(content) or {}
    
    agent = registry.get("agents", {}).get(name)
    
    if not agent:
        return f"Subagent type '{name}' not found in registry."
    
    # Check container status
    returncode, stdout, stderr = await _run_command(
        ["docker", "inspect", f"ravenhelm-{name}", "--format", "{{.State.Status}}"],
        timeout=10
    )
    container_status = stdout.strip() if returncode == 0 else "not found"
    
    # Check health endpoint
    port = agent.get("port")
    health_status = "unknown"
    if port and container_status == "running":
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"http://localhost:{port}/info", timeout=5.0)
                health_status = "healthy" if resp.status_code == 200 else "unhealthy"
        except:
            health_status = "unhealthy"
    
    lines = [
        f"# {agent.get('name', name)} Status",
        "",
        f"**Registry Status:** {agent.get('status', 'unknown')}",
        f"**Container Status:** {container_status}",
        f"**Health Check:** {health_status}",
        f"**Port:** {port}",
        f"**Image:** {agent.get('container', {}).get('image', 'N/A')}",
        "",
        f"**Model:** {agent.get('model')}",
        f"**Skills:** {', '.join(agent.get('skills', []))}",
        f"**Tools:** {', '.join(agent.get('tools', []))}",
    ]
    
    return "\n".join(lines)


@tool
async def stop_subagent(name: str) -> str:
    """Stop a running subagent container.
    
    Args:
        name: The kebab-case name of the subagent type
    """
    returncode, stdout, stderr = await _run_command(
        ["docker", "stop", f"ravenhelm-{name}"],
        timeout=30
    )
    
    if returncode == 0:
        # Update registry
        agent_registry_path = CONFIG_DIR / "agent_registry.yaml"
        if await _path_exists(agent_registry_path):
            content = await _read_text(agent_registry_path)
            registry = yaml.safe_load(content) or {}
            
            if name in registry.get("agents", {}):
                registry["agents"][name]["status"] = "stopped"
                await _write_text(agent_registry_path, yaml.dump(registry, default_flow_style=False, sort_keys=False))
        
        return f"✓ Subagent '{name}' stopped successfully."
    else:
        return f"✗ Failed to stop: {stderr}"


@tool
async def start_subagent(name: str) -> str:
    """Start a stopped subagent container.
    
    Args:
        name: The kebab-case name of the subagent type
    """
    returncode, stdout, stderr = await _run_command(
        ["docker", "start", f"ravenhelm-{name}"],
        timeout=30
    )
    
    if returncode == 0:
        # Update registry
        agent_registry_path = CONFIG_DIR / "agent_registry.yaml"
        if await _path_exists(agent_registry_path):
            content = await _read_text(agent_registry_path)
            registry = yaml.safe_load(content) or {}
            
            if name in registry.get("agents", {}):
                registry["agents"][name]["status"] = "running"
                await _write_text(agent_registry_path, yaml.dump(registry, default_flow_style=False, sort_keys=False))
        
        return f"✓ Subagent '{name}' started successfully."
    else:
        return f"✗ Failed to start: {stderr}"


@tool
async def delete_subagent_type(name: str, remove_code: bool = False) -> str:
    """Delete a subagent type completely.
    
    This will:
    1. Stop and remove the container
    2. Remove the Docker image
    3. Remove from registries
    4. Optionally delete the source code
    
    Args:
        name: The kebab-case name of the subagent type
        remove_code: Whether to also delete the agent source code (default: False)
    """
    results = [f"Deleting subagent type '{name}'...", ""]
    
    # Stop and remove container
    await _run_command(["docker", "stop", f"ravenhelm-{name}"], timeout=30)
    await _run_command(["docker", "rm", f"ravenhelm-{name}"], timeout=30)
    results.append("✓ Container removed")
    
    # Remove image
    await _run_command(["docker", "rmi", f"ravenhelm/{name}:latest"], timeout=30)
    results.append("✓ Image removed (if existed)")
    
    # Update port registry
    port_registry_path = CONFIG_DIR / "port_registry.yaml"
    if await _path_exists(port_registry_path):
        content = await _read_text(port_registry_path)
        registry = yaml.safe_load(content) or {}
        
        if name in registry.get("agents", {}):
            del registry["agents"][name]
            await _write_text(port_registry_path, yaml.dump(registry, default_flow_style=False, sort_keys=False))
            results.append("✓ Removed from port registry")
    
    # Update agent registry
    agent_registry_path = CONFIG_DIR / "agent_registry.yaml"
    if await _path_exists(agent_registry_path):
        content = await _read_text(agent_registry_path)
        registry = yaml.safe_load(content) or {}
        
        if name in registry.get("agents", {}):
            del registry["agents"][name]
            await _write_text(agent_registry_path, yaml.dump(registry, default_flow_style=False, sort_keys=False))
            results.append("✓ Removed from agent registry")
    
    # Remove source code
    if remove_code:
        agent_dir = AGENTS_DIR / name
        if await _path_exists(agent_dir):
            await _rmtree(agent_dir)
            results.append(f"✓ Source code removed from {agent_dir}")
    
    results.append("")
    results.append(f"Subagent type '{name}' has been deleted.")
    
    return "\n".join(results)


# =============================================================================
# Tool Collection
# =============================================================================

SUBAGENT_SPAWNER_TOOLS = [
    spawn_subagent_type,
    list_subagent_types,
    get_subagent_status,
    start_subagent,
    stop_subagent,
    delete_subagent_type,
]

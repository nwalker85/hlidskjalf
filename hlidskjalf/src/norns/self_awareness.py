"""
Self-Awareness Module for Norns Agent

This module enables the Norns to:
- Introspect its own source code
- View its configuration and capabilities
- Modify its own code
- Trigger reloads for self-improvement

"Know thyself" - Inscribed on the Temple of Apollo at Delphi

All file operations are async to avoid blocking the event loop.
"""

import os
import sys
import inspect
import importlib
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


async def _path_is_dir(path: Path) -> bool:
    """Async check if path is a directory."""
    return await asyncio.to_thread(path.is_dir)


async def _list_dir(path: Path) -> list[Path]:
    """Async directory listing."""
    return await asyncio.to_thread(lambda: list(path.iterdir()))


async def _read_text(path: Path) -> str:
    """Async file read."""
    async with aiofiles.open(path, mode='r', encoding='utf-8', errors='ignore') as f:
        return await f.read()


async def _write_text(path: Path, content: str) -> None:
    """Async file write."""
    async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
        await f.write(content)


async def _mkdir(path: Path, parents: bool = False, exist_ok: bool = False) -> None:
    """Async directory creation."""
    await asyncio.to_thread(path.mkdir, parents=parents, exist_ok=exist_ok)


async def _stat_mtime(path: Path) -> float:
    """Async get file modification time."""
    stat = await asyncio.to_thread(path.stat)
    return stat.st_mtime


async def _glob(path: Path, pattern: str) -> list[Path]:
    """Async glob."""
    return await asyncio.to_thread(lambda: list(path.glob(pattern)))


# =============================================================================
# Path Configuration
# =============================================================================

# The Norns' home - where its source code lives
NORNS_SOURCE_DIR = Path(__file__).parent
HLIDSKJALF_ROOT = NORNS_SOURCE_DIR.parent.parent
WORKSPACE_ROOT = HLIDSKJALF_ROOT.parent

# Key source files the Norns should know about
SELF_FILES = {
    "agent": NORNS_SOURCE_DIR / "agent.py",
    "tools": NORNS_SOURCE_DIR / "tools.py",
    "skills": NORNS_SOURCE_DIR / "skills.py",
    "planner": NORNS_SOURCE_DIR / "planner.py",
    "self_awareness": NORNS_SOURCE_DIR / "self_awareness.py",
    "subagent_spawner": NORNS_SOURCE_DIR / "subagent_spawner.py",
}

# Configuration files
CONFIG_FILES = {
    "langgraph_config": WORKSPACE_ROOT / "langgraph.json",
    "pyproject": HLIDSKJALF_ROOT / "pyproject.toml",
    "docker_compose": WORKSPACE_ROOT / "docker-compose.yml",
}


# =============================================================================
# Introspection Tools
# =============================================================================

@tool
async def view_self_source(component: str = "agent") -> str:
    """View the Norns' own source code.
    
    Use this to understand how you work, find bugs, or plan improvements.
    
    Args:
        component: Which part of yourself to view. Options:
            - 'agent': Main agent logic and state machine
            - 'tools': Available tools and their implementations
            - 'skills': Skills system for learning
            - 'planner': Planning and TODO generation
            - 'self_awareness': This module (meta!)
            - 'subagent_spawner': Subagent creation tools
            - 'all': List all available components
    
    Returns:
        The source code of the requested component
    """
    if component == "all":
        lines = ["# Norns Source Components\n"]
        lines.append("## Core Modules")
        for name, path in SELF_FILES.items():
            exists = "✓" if await _path_exists(path) else "✗"
            lines.append(f"  - {name}: {path} [{exists}]")
        
        lines.append("\n## Configuration Files")
        for name, path in CONFIG_FILES.items():
            exists = "✓" if await _path_exists(path) else "✗"
            lines.append(f"  - {name}: {path} [{exists}]")
        
        lines.append("\n## Skills Directory")
        skills_dir = HLIDSKJALF_ROOT / "skills"
        if await _path_exists(skills_dir):
            items = await _list_dir(skills_dir)
            for skill in items:
                if await _path_is_dir(skill):
                    skill_md = skill / "SKILL.md"
                    if await _path_exists(skill_md):
                        lines.append(f"  - {skill.name}/")
        
        return "\n".join(lines)
    
    if component not in SELF_FILES:
        return f"Unknown component '{component}'. Available: {', '.join(SELF_FILES.keys())}, 'all'"
    
    source_path = SELF_FILES[component]
    
    if not await _path_exists(source_path):
        return f"Source file not found: {source_path}"
    
    content = await _read_text(source_path)
    line_count = len(content.splitlines())
    mtime = await _stat_mtime(source_path)
    
    return f"""# {component}.py
# Path: {source_path}
# Lines: {line_count}
# Last modified: {datetime.fromtimestamp(mtime).isoformat()}

{content}"""


@tool
async def view_self_config(config: str = "langgraph_config") -> str:
    """View the Norns' configuration files.
    
    Args:
        config: Which config to view. Options:
            - 'langgraph_config': LangGraph server configuration
            - 'pyproject': Python project dependencies
            - 'docker_compose': Docker services configuration
    
    Returns:
        The configuration file contents
    """
    if config not in CONFIG_FILES:
        return f"Unknown config '{config}'. Available: {', '.join(CONFIG_FILES.keys())}"
    
    config_path = CONFIG_FILES[config]
    
    if not await _path_exists(config_path):
        return f"Config file not found: {config_path}"
    
    content = await _read_text(config_path)
    
    return f"""# {config_path.name}
# Path: {config_path}

{content}"""


@tool
async def introspect_capabilities() -> str:
    """Get a summary of all current capabilities, tools, and skills.
    
    Use this to understand what you can do right now.
    
    Returns:
        A comprehensive summary of capabilities
    """
    lines = ["# Norns Capabilities Summary\n"]
    
    # Tools from tools.py
    lines.append("## Available Tools")
    tools_path = SELF_FILES["tools"]
    if await _path_exists(tools_path):
        content = await _read_text(tools_path)
        # Count @tool decorators
        tool_count = content.count("@tool")
        lines.append(f"  Total tools: ~{tool_count}")
    
    # Skills
    lines.append("\n## Learned Skills")
    skills_dir = HLIDSKJALF_ROOT / "skills"
    if await _path_exists(skills_dir):
        items = await _list_dir(skills_dir)
        skill_count = 0
        for skill in items:
            if await _path_is_dir(skill):
                skill_md = skill / "SKILL.md"
                if await _path_exists(skill_md):
                    skill_count += 1
                    lines.append(f"  - {skill.name}")
        if skill_count == 0:
            lines.append("  No skills learned yet")
    
    # Self-awareness capabilities
    lines.append("\n## Self-Awareness")
    lines.append("  - Can view own source code")
    lines.append("  - Can view configuration")
    lines.append("  - Can modify own code")
    lines.append("  - Can create new skills")
    lines.append("  - Can spawn subagents")
    
    return "\n".join(lines)


# =============================================================================
# Self-Modification Tools
# =============================================================================

@tool
async def modify_self_source(
    component: str,
    search_text: str,
    replace_text: str,
    reason: str
) -> str:
    """Modify the Norns' own source code.
    
    ⚠️ CAUTION: This modifies actual source files. Use carefully!
    
    Args:
        component: Which component to modify (agent, tools, skills, etc.)
        search_text: The exact text to find and replace
        replace_text: The new text to insert
        reason: Explanation of why this change is needed
    
    Returns:
        Result of the modification attempt
    """
    if component not in SELF_FILES:
        return f"Unknown component '{component}'. Available: {', '.join(SELF_FILES.keys())}"
    
    source_path = SELF_FILES[component]
    
    if not await _path_exists(source_path):
        return f"Source file not found: {source_path}"
    
    content = await _read_text(source_path)
    
    if search_text not in content:
        return f"Search text not found in {component}.py. Make sure the text matches exactly."
    
    # Create backup
    backup_dir = NORNS_SOURCE_DIR / ".backups"
    await _mkdir(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{component}_{timestamp}.py"
    await _write_text(backup_path, content)
    
    # Apply modification
    new_content = content.replace(search_text, replace_text, 1)
    await _write_text(source_path, new_content)
    
    # Log the change
    changelog_path = NORNS_SOURCE_DIR / ".changelog"
    await _mkdir(changelog_path, exist_ok=True)
    
    log_entry = f"""## {datetime.now().isoformat()}
Component: {component}
Reason: {reason}
Backup: {backup_path}

### Search Text
```
{search_text[:500]}{'...' if len(search_text) > 500 else ''}
```

### Replace Text  
```
{replace_text[:500]}{'...' if len(replace_text) > 500 else ''}
```

---
"""
    log_file = changelog_path / f"{timestamp}.md"
    await _write_text(log_file, log_entry)
    
    return f"""✓ Successfully modified {component}.py

**Reason:** {reason}
**Backup saved to:** {backup_path}
**Change logged to:** {log_file}

⚠️ Changes take effect after reload. Use `trigger_self_reload()` if needed."""


@tool
async def add_tool_to_self(
    tool_name: str,
    tool_code: str,
    description: str
) -> str:
    """Add a new tool to the Norns' capabilities.
    
    This appends a new @tool function to tools.py.
    
    Args:
        tool_name: Name for the new tool (snake_case)
        tool_code: The complete tool function code including @tool decorator
        description: What this tool does
    
    Returns:
        Result of adding the tool
    """
    tools_path = SELF_FILES["tools"]
    
    if not await _path_exists(tools_path):
        return f"Tools file not found: {tools_path}"
    
    content = await _read_text(tools_path)
    
    # Validate tool code has @tool decorator
    if "@tool" not in tool_code:
        return "Tool code must include @tool decorator"
    
    if f"def {tool_name}" in content:
        return f"Tool '{tool_name}' already exists in tools.py"
    
    # Create backup
    backup_dir = NORNS_SOURCE_DIR / ".backups"
    await _mkdir(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"tools_{timestamp}.py"
    await _write_text(backup_path, content)
    
    # Add tool before the NORN_TOOLS list
    marker = "# =============================================================================\n# COMBINED TOOLS"
    if marker not in content:
        marker = "NORN_TOOLS = ["
    
    new_tool_section = f"""
# =============================================================================
# {description}
# Added: {datetime.now().isoformat()}
# =============================================================================

{tool_code}

"""
    
    new_content = content.replace(marker, new_tool_section + marker)
    await _write_text(tools_path, new_content)
    
    return f"""✓ Successfully added tool '{tool_name}' to tools.py

**Description:** {description}
**Backup saved to:** {backup_path}

⚠️ Don't forget to add '{tool_name}' to NORN_TOOLS list and reload!"""


@tool
async def revert_self_change(backup_file: Optional[str] = None) -> str:
    """Revert to a previous version of source code.
    
    Args:
        backup_file: Specific backup file to restore, or None to list available backups
    
    Returns:
        List of backups or result of restore
    """
    backup_dir = NORNS_SOURCE_DIR / ".backups"
    
    if not await _path_exists(backup_dir):
        return "No backups found. The .backups directory doesn't exist."
    
    backups = await _glob(backup_dir, "*.py")
    
    if not backup_file:
        if not backups:
            return "No backup files found."
        
        lines = ["# Available Backups\n"]
        for backup in sorted(backups, reverse=True)[:20]:
            mtime = await _stat_mtime(backup)
            lines.append(f"  - {backup.name} ({datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')})")
        
        lines.append("\nUse revert_self_change(backup_file='filename.py') to restore")
        return "\n".join(lines)
    
    backup_path = backup_dir / backup_file
    if not await _path_exists(backup_path):
        return f"Backup file not found: {backup_file}"
    
    # Determine which component this backup is for
    component = backup_file.split("_")[0]
    if component not in SELF_FILES:
        return f"Cannot determine component for backup: {backup_file}"
    
    source_path = SELF_FILES[component]
    backup_content = await _read_text(backup_path)
    
    # Create a backup of current state before reverting
    current_content = await _read_text(source_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre_revert_backup = backup_dir / f"{component}_prerevert_{timestamp}.py"
    await _write_text(pre_revert_backup, current_content)
    
    # Restore
    await _write_text(source_path, backup_content)
    
    return f"""✓ Reverted {component}.py to {backup_file}

**Pre-revert backup saved to:** {pre_revert_backup}

⚠️ Changes take effect after reload."""


@tool
async def view_self_history() -> str:
    """View the changelog of self-modifications.
    
    Returns:
        Recent modification history
    """
    changelog_dir = NORNS_SOURCE_DIR / ".changelog"
    
    if not await _path_exists(changelog_dir):
        return "No modification history found."
    
    logs = await _glob(changelog_dir, "*.md")
    
    if not logs:
        return "No modification logs found."
    
    lines = ["# Self-Modification History\n"]
    
    # Get the 10 most recent logs
    sorted_logs = sorted(logs, reverse=True)[:10]
    
    for log_file in sorted_logs:
        content = await _read_text(log_file)
        lines.append(content[:1000])  # Truncate long entries
        lines.append("\n---\n")
    
    backup_dir = NORNS_SOURCE_DIR / ".backups"
    if await _path_exists(backup_dir):
        backups = await _glob(backup_dir, "*.py")
        lines.append(f"\n**{len(backups)} backup files available**")
    
    return "\n".join(lines)


@tool
async def trigger_self_reload() -> str:
    """Request a reload of modified modules.
    
    ⚠️ This attempts to reload Python modules. May not work for all changes.
    Some changes require a full server restart.
    
    Returns:
        Result of reload attempt
    """
    results = []
    
    for name, path in SELF_FILES.items():
        if not await _path_exists(path):
            continue
            
        module_name = f"src.norns.{name}"
        
        try:
            if module_name in sys.modules:
                # Run importlib.reload in thread to avoid blocking
                await asyncio.to_thread(importlib.reload, sys.modules[module_name])
                results.append(f"✓ Reloaded {module_name}")
            else:
                results.append(f"⊘ {module_name} not loaded")
        except Exception as e:
            results.append(f"✗ Failed to reload {module_name}: {e}")
    
    results.append("\n⚠️ Note: For major changes, a full server restart may be required.")
    results.append("Run: docker compose restart langgraph")
    
    return "\n".join(results)


@tool
async def get_self_diff(component: str = "agent") -> str:
    """Get the diff between current source and most recent backup.
    
    Args:
        component: Which component to diff
    
    Returns:
        Diff output or message if no backups exist
    """
    if component not in SELF_FILES:
        return f"Unknown component '{component}'. Available: {', '.join(SELF_FILES.keys())}"
    
    source_path = SELF_FILES[component]
    backup_dir = NORNS_SOURCE_DIR / ".backups"
    
    if not await _path_exists(backup_dir):
        return "No backups found to compare against."
    
    # Find most recent backup for this component
    backups = await _glob(backup_dir, f"{component}_*.py")
    
    if not backups:
        return f"No backups found for {component}"
    
    latest_backup = sorted(backups)[-1]
    
    current = await _read_text(source_path)
    backup = await _read_text(latest_backup)
    
    if current == backup:
        return f"No changes since last backup ({latest_backup.name})"
    
    # Simple line-by-line diff
    current_lines = current.splitlines()
    backup_lines = backup.splitlines()
    
    diff_lines = [f"# Diff: {component}.py vs {latest_backup.name}\n"]
    
    import difflib
    diff = difflib.unified_diff(
        backup_lines,
        current_lines,
        fromfile=f"{latest_backup.name}",
        tofile=f"{component}.py",
        lineterm=""
    )
    
    diff_lines.extend(diff)
    
    return "\n".join(diff_lines) if len(diff_lines) > 1 else "No differences found."


# =============================================================================
# Tool Collection
# =============================================================================

SELF_AWARENESS_TOOLS = [
    view_self_source,
    view_self_config,
    introspect_capabilities,
    modify_self_source,
    add_tool_to_self,
    revert_self_change,
    view_self_history,
    trigger_self_reload,
    get_self_diff,
]

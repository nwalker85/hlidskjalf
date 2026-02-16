"""
Norns Tools API - Tool introspection endpoint.

Provides tool definitions for the Bifrost registry to discover.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from src.norns.tools import NORN_TOOLS

logger = logging.getLogger(__name__)

# Create router for tool introspection
router = APIRouter(prefix="/tools", tags=["tools"])


def _categorize_tool(name: str) -> str:
    """Infer tool category from name."""
    name_lower = name.lower()
    
    # Verðandi - Platform observation
    if any(x in name_lower for x in ["platform", "deployment", "health", "project", "list_projects", "get_project"]):
        return "platform"
    
    # Urðr - History/logs
    if any(x in name_lower for x in ["log", "history", "trend", "analyze"]):
        return "history"
    
    # Skuld - Planning/future
    if any(x in name_lower for x in ["plan", "allocate", "generate", "register", "predict", "nginx"]):
        return "planning"
    
    # Memory tools
    if any(x in name_lower for x in ["huginn", "frigg", "muninn", "hel", "mimir", "memory"]):
        return "memory"
    
    # Skills
    if any(x in name_lower for x in ["skill", "procedural"]):
        return "skills"
    
    # Workspace
    if any(x in name_lower for x in ["workspace", "file", "directory"]):
        return "workspace"
    
    # Web/Documents
    if any(x in name_lower for x in ["document", "crawl", "web"]):
        return "web"
    
    # Graph
    if any(x in name_lower for x in ["graph"]):
        return "graph"
    
    # Ollama
    if any(x in name_lower for x in ["ollama"]):
        return "llm"
    
    # Subagents
    if any(x in name_lower for x in ["subagent", "spawn"]):
        return "subagents"
    
    return "custom"


def _extract_docstring_parts(docstring: str | None) -> tuple[str, str]:
    """Extract description and norn persona from docstring."""
    if not docstring:
        return "", ""
    
    lines = docstring.strip().split('\n')
    description = ""
    norn = ""
    
    for line in lines:
        line = line.strip()
        if line.startswith("[") and "]" in line:
            # Extract norn persona like [Verðandi]
            norn_part = line.split("]")[0].replace("[", "")
            norn = norn_part.lower()
            # Rest is description
            rest = line.split("]", 1)[1].strip() if "]" in line else ""
            if rest:
                description = rest
        elif line and not description:
            description = line
    
    return description, norn


def get_tool_definitions() -> list[dict[str, Any]]:
    """
    Extract tool definitions from NORN_TOOLS.
    
    Returns list of tool definitions suitable for registry consumption.
    """
    tools = []
    
    for tool in NORN_TOOLS:
        try:
            # Extract basic info
            name = tool.name
            docstring = tool.description or ""
            description, norn = _extract_docstring_parts(docstring)
            
            # Get parameter schema
            parameters = {}
            if hasattr(tool, 'args_schema') and tool.args_schema:
                try:
                    schema = tool.args_schema.model_json_schema()
                    parameters = schema
                except Exception:
                    parameters = {}
            
            # Build tool definition
            tool_def = {
                "name": name,
                "description": description or docstring[:200],
                "full_description": docstring,
                "category": _categorize_tool(name),
                "norn": norn,  # verðandi, urðr, skuld, or empty
                "enabled": True,
                "parameters": parameters,
                "tags": [],
            }
            
            # Add tags based on category and norn
            if norn:
                tool_def["tags"].append(f"norn:{norn}")
            tool_def["tags"].append(f"category:{tool_def['category']}")
            
            tools.append(tool_def)
            
        except Exception as e:
            logger.warning(f"Failed to extract tool '{getattr(tool, 'name', 'unknown')}': {e}")
    
    return tools


@router.get("")
async def list_tools():
    """
    List all available Norns tools.
    
    Used by Bifrost registry to discover tools.
    """
    tools = get_tool_definitions()
    
    return {
        "tools": tools,
        "total": len(tools),
        "version": "1.0.0",
    }


@router.get("/categories")
async def get_categories():
    """Get tool count by category."""
    tools = get_tool_definitions()
    
    categories: dict[str, int] = {}
    for tool in tools:
        cat = tool.get("category", "custom")
        categories[cat] = categories.get(cat, 0) + 1
    
    return {"categories": categories}


@router.get("/{tool_name}")
async def get_tool(tool_name: str):
    """Get details for a specific tool."""
    tools = get_tool_definitions()
    
    for tool in tools:
        if tool["name"] == tool_name:
            return tool
    
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")


def get_tools_router() -> APIRouter:
    """Get the tools router for mounting."""
    return router


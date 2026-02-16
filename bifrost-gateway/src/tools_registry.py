"""
Bifrost Tool Registry - Central registry for all available tools.

Provides:
- Tool registration and discovery
- MCP tool integration
- Enable/disable management
- Tool introspection endpoints
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """Tool category classifications."""
    PLATFORM = "platform"       # Platform observation (Verðandi)
    HISTORY = "history"         # Past analysis (Urðr)
    PLANNING = "planning"       # Future planning (Skuld)
    MEMORY = "memory"          # Cognitive memory (Huginn, Frigg, Muninn, etc.)
    SKILLS = "skills"          # Skill retrieval and management
    WORKSPACE = "workspace"    # File/directory operations
    WEB = "web"                # Web crawling and document ingestion
    GRAPH = "graph"            # Graph/Neo4j queries
    LLM = "llm"                # Local LLM (Ollama)
    SUBAGENTS = "subagents"    # Subagent spawning
    MCP = "mcp"                # External MCP tools
    CUSTOM = "custom"          # User-defined tools


class ToolSource(str, Enum):
    """Source of tool definition."""
    NORNS = "norns"            # Built into Norns agent
    BIFROST = "bifrost"        # Provided by Bifrost adapters
    MCP = "mcp"                # External MCP server
    CUSTOM = "custom"          # User-defined


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    description: str = ""
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


@dataclass
class ToolDefinition:
    """Complete definition of a tool."""
    name: str
    description: str
    category: ToolCategory
    source: ToolSource
    enabled: bool = True
    parameters: list[ToolParameter] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)  # Dependencies
    tags: list[str] = field(default_factory=list)
    version: str = "1.0.0"
    mcp_server: str | None = None  # For MCP tools
    endpoint: str | None = None  # For custom tools
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "source": self.source.value,
            "enabled": self.enabled,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "enum": p.enum,
                }
                for p in self.parameters
            ],
            "requires": self.requires,
            "tags": self.tags,
            "version": self.version,
            "mcp_server": self.mcp_server,
            "endpoint": self.endpoint,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolDefinition":
        """Create from dictionary."""
        params = [
            ToolParameter(
                name=p["name"],
                type=p.get("type", "string"),
                description=p.get("description", ""),
                required=p.get("required", True),
                default=p.get("default"),
                enum=p.get("enum"),
            )
            for p in data.get("parameters", [])
        ]
        
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            category=ToolCategory(data.get("category", "custom")),
            source=ToolSource(data.get("source", "custom")),
            enabled=data.get("enabled", True),
            parameters=params,
            requires=data.get("requires", []),
            tags=data.get("tags", []),
            version=data.get("version", "1.0.0"),
            mcp_server=data.get("mcp_server"),
            endpoint=data.get("endpoint"),
        )


class ToolRegistry:
    """
    Central registry for all available tools.
    
    Combines:
    - Built-in Norns tools (discovered via API)
    - MCP tools from external servers
    - Custom user-defined tools
    """
    
    def __init__(
        self,
        norns_url: str = "http://norns.ravenhelm.test",
        redis_url: str | None = None,
    ):
        self.norns_url = norns_url
        self.redis_url = redis_url
        
        # In-memory registry
        self._tools: dict[str, ToolDefinition] = {}
        self._mcp_servers: dict[str, str] = {}  # name -> url
        
        # Disabled tools (persisted to Redis)
        self._disabled: set[str] = set()
        
        # Redis client for persistence (lazy init)
        self._redis = None
    
    async def _get_redis(self):
        """Get or create Redis connection."""
        if self._redis is None and self.redis_url:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self.redis_url, decode_responses=True)
            except ImportError:
                logger.warning("redis.asyncio not available, tool state not persisted")
        return self._redis
    
    async def _load_state(self):
        """Load disabled tools from Redis."""
        r = await self._get_redis()
        if r:
            try:
                disabled = await r.smembers("bifrost:tools:disabled")
                self._disabled = set(disabled) if disabled else set()
            except Exception as e:
                logger.warning(f"Failed to load tool state: {e}")
    
    async def _save_state(self):
        """Save disabled tools to Redis."""
        r = await self._get_redis()
        if r:
            try:
                await r.delete("bifrost:tools:disabled")
                if self._disabled:
                    await r.sadd("bifrost:tools:disabled", *self._disabled)
            except Exception as e:
                logger.warning(f"Failed to save tool state: {e}")
    
    def register_tool(self, tool: ToolDefinition) -> bool:
        """
        Register a tool in the registry.
        
        Returns True if registration succeeded.
        """
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, updating")
        
        self._tools[tool.name] = tool
        
        # Apply disabled state
        if tool.name in self._disabled:
            tool.enabled = False
        
        logger.info(f"Registered tool: {tool.name} ({tool.category.value})")
        return True
    
    def unregister_tool(self, name: str) -> bool:
        """
        Remove a tool from the registry.
        
        Returns True if tool was found and removed.
        """
        if name in self._tools:
            del self._tools[name]
            self._disabled.discard(name)
            logger.info(f"Unregistered tool: {name}")
            return True
        return False
    
    async def enable_tool(self, name: str) -> bool:
        """Enable a tool."""
        if name in self._tools:
            self._tools[name].enabled = True
            self._disabled.discard(name)
            await self._save_state()
            logger.info(f"Enabled tool: {name}")
            return True
        return False
    
    async def disable_tool(self, name: str) -> bool:
        """Disable a tool."""
        if name in self._tools:
            self._tools[name].enabled = False
            self._disabled.add(name)
            await self._save_state()
            logger.info(f"Disabled tool: {name}")
            return True
        return False
    
    def get_tool(self, name: str) -> ToolDefinition | None:
        """Get a single tool by name."""
        return self._tools.get(name)
    
    def list_tools(
        self,
        category: ToolCategory | None = None,
        source: ToolSource | None = None,
        enabled_only: bool = False,
        tag: str | None = None,
    ) -> list[ToolDefinition]:
        """
        List tools with optional filters.
        
        Args:
            category: Filter by category
            source: Filter by source
            enabled_only: Only return enabled tools
            tag: Filter by tag
        """
        tools = list(self._tools.values())
        
        if category:
            tools = [t for t in tools if t.category == category]
        
        if source:
            tools = [t for t in tools if t.source == source]
        
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        
        if tag:
            tools = [t for t in tools if tag in t.tags]
        
        return sorted(tools, key=lambda t: (t.category.value, t.name))
    
    def get_categories(self) -> dict[str, int]:
        """Get tool counts by category."""
        counts: dict[str, int] = {}
        for tool in self._tools.values():
            cat = tool.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts
    
    async def discover_norns_tools(self) -> int:
        """
        Discover tools from Norns agent.
        
        Returns number of tools discovered.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(f"{self.norns_url}/tools")
                
                if resp.status_code != 200:
                    logger.warning(f"Failed to fetch Norns tools: {resp.status_code}")
                    return 0
                
                tools_data = resp.json()
                count = 0
                
                for tool_data in tools_data.get("tools", []):
                    tool = self._convert_norns_tool(tool_data)
                    if tool:
                        self.register_tool(tool)
                        count += 1
                
                logger.info(f"Discovered {count} Norns tools")
                return count
                
        except httpx.ConnectError:
            logger.warning(f"Cannot connect to Norns at {self.norns_url}")
            return 0
        except Exception as e:
            logger.error(f"Error discovering Norns tools: {e}")
            return 0
    
    def _convert_norns_tool(self, data: dict[str, Any]) -> ToolDefinition | None:
        """Convert Norns tool data to ToolDefinition."""
        try:
            name = data.get("name", "")
            if not name:
                return None
            
            # Infer category from tool name or description
            category = self._infer_category(name, data.get("description", ""))
            
            # Parse parameters from schema
            params = []
            schema = data.get("parameters", {})
            if isinstance(schema, dict):
                for prop_name, prop_schema in schema.get("properties", {}).items():
                    required_list = schema.get("required", [])
                    params.append(ToolParameter(
                        name=prop_name,
                        type=prop_schema.get("type", "string"),
                        description=prop_schema.get("description", ""),
                        required=prop_name in required_list,
                        default=prop_schema.get("default"),
                        enum=prop_schema.get("enum"),
                    ))
            
            return ToolDefinition(
                name=name,
                description=data.get("description", ""),
                category=category,
                source=ToolSource.NORNS,
                enabled=data.get("enabled", True),
                parameters=params,
                tags=data.get("tags", []),
            )
        except Exception as e:
            logger.warning(f"Failed to convert tool: {e}")
            return None
    
    def _infer_category(self, name: str, description: str) -> ToolCategory:
        """Infer tool category from name and description."""
        name_lower = name.lower()
        desc_lower = description.lower()
        
        # Verðandi - Platform observation
        if any(x in name_lower for x in ["platform", "deployment", "health", "project"]):
            return ToolCategory.PLATFORM
        
        # Urðr - History/logs
        if any(x in name_lower for x in ["log", "history", "trend", "analyze"]):
            return ToolCategory.HISTORY
        
        # Skuld - Planning/future
        if any(x in name_lower for x in ["plan", "allocate", "generate", "register", "predict"]):
            return ToolCategory.PLANNING
        
        # Memory tools
        if any(x in name_lower for x in ["huginn", "frigg", "muninn", "hel", "mimir", "memory"]):
            return ToolCategory.MEMORY
        
        # Skills
        if any(x in name_lower for x in ["skill", "procedural"]):
            return ToolCategory.SKILLS
        
        # Workspace
        if any(x in name_lower for x in ["workspace", "file", "directory"]):
            return ToolCategory.WORKSPACE
        
        # Web/Documents
        if any(x in name_lower for x in ["document", "crawl", "web"]):
            return ToolCategory.WEB
        
        # Graph
        if any(x in name_lower for x in ["graph", "neo4j"]):
            return ToolCategory.GRAPH
        
        # Ollama
        if any(x in name_lower for x in ["ollama"]):
            return ToolCategory.LLM
        
        # Subagents
        if any(x in name_lower for x in ["subagent", "spawn"]):
            return ToolCategory.SUBAGENTS
        
        return ToolCategory.CUSTOM
    
    def add_mcp_server(self, name: str, url: str):
        """Register an MCP server for tool discovery."""
        self._mcp_servers[name] = url
        logger.info(f"Added MCP server: {name} at {url}")
    
    async def discover_mcp_tools(self, server_name: str | None = None) -> int:
        """
        Discover tools from MCP servers.
        
        Args:
            server_name: Specific server to query, or None for all
            
        Returns number of tools discovered.
        """
        servers = (
            {server_name: self._mcp_servers[server_name]}
            if server_name and server_name in self._mcp_servers
            else self._mcp_servers
        )
        
        total_count = 0
        
        for name, url in servers.items():
            try:
                count = await self._discover_single_mcp(name, url)
                total_count += count
            except Exception as e:
                logger.error(f"Failed to discover MCP tools from {name}: {e}")
        
        return total_count
    
    async def _discover_single_mcp(self, server_name: str, url: str) -> int:
        """Discover tools from a single MCP server."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # MCP uses JSON-RPC - call tools/list
                resp = await client.post(
                    url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/list",
                    },
                )
                
                if resp.status_code != 200:
                    logger.warning(f"MCP server {server_name} returned {resp.status_code}")
                    return 0
                
                result = resp.json()
                tools_list = result.get("result", {}).get("tools", [])
                count = 0
                
                for mcp_tool in tools_list:
                    tool = self._convert_mcp_tool(mcp_tool, server_name)
                    if tool:
                        self.register_tool(tool)
                        count += 1
                
                logger.info(f"Discovered {count} tools from MCP server {server_name}")
                return count
                
        except httpx.ConnectError:
            logger.warning(f"Cannot connect to MCP server {server_name} at {url}")
            return 0
        except Exception as e:
            logger.error(f"Error querying MCP server {server_name}: {e}")
            return 0
    
    def _convert_mcp_tool(self, data: dict[str, Any], server_name: str) -> ToolDefinition | None:
        """Convert MCP tool to ToolDefinition."""
        try:
            name = data.get("name", "")
            if not name:
                return None
            
            # Parse input schema
            params = []
            input_schema = data.get("inputSchema", {})
            if isinstance(input_schema, dict):
                for prop_name, prop_schema in input_schema.get("properties", {}).items():
                    required_list = input_schema.get("required", [])
                    params.append(ToolParameter(
                        name=prop_name,
                        type=prop_schema.get("type", "string"),
                        description=prop_schema.get("description", ""),
                        required=prop_name in required_list,
                    ))
            
            return ToolDefinition(
                name=f"mcp_{server_name}_{name}",
                description=data.get("description", ""),
                category=ToolCategory.MCP,
                source=ToolSource.MCP,
                enabled=True,
                parameters=params,
                mcp_server=server_name,
                tags=[f"mcp:{server_name}"],
            )
        except Exception as e:
            logger.warning(f"Failed to convert MCP tool: {e}")
            return None
    
    async def initialize(self):
        """Initialize registry with all known tools."""
        await self._load_state()
        
        # Discover Norns tools
        await self.discover_norns_tools()
        
        # Discover MCP tools
        await self.discover_mcp_tools()
        
        logger.info(f"Tool registry initialized with {len(self._tools)} tools")


# Global registry instance
_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _registry
    if _registry is None:
        from src.config import get_settings
        settings = get_settings()
        _registry = ToolRegistry(
            norns_url=getattr(settings, 'NORNS_URL', 'http://norns.ravenhelm.test'),
            redis_url=getattr(settings, 'REDIS_URL', None),
        )
    return _registry


async def initialize_registry():
    """Initialize the global tool registry."""
    registry = get_tool_registry()
    await registry.initialize()
    return registry


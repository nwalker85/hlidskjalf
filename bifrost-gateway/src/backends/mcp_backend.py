"""
MCP Backend — Integration via Model Context Protocol.

This backend connects to any AI system that exposes an MCP server,
allowing Bifrost to communicate with diverse AI implementations
through a standardized protocol.

MCP (Model Context Protocol) is a standard for AI tool/resource access:
https://modelcontextprotocol.io/
"""

from typing import AsyncIterator, Optional, Any
import json

import httpx
import structlog

from src.backends.base import (
    BaseBackend,
    BackendCapabilities,
    BackendConfig,
    ChatRequest,
    ChatResponse,
)
from src.backends.registry import register_backend

logger = structlog.get_logger(__name__)


@register_backend("mcp")
class MCPBackend(BaseBackend):
    """
    Backend for MCP-compatible AI systems.
    
    Connects to an MCP server and uses the chat/completion tools
    to communicate with the underlying AI.
    
    Configuration:
        api_url: URL of the MCP server (e.g., http://localhost:3000)
        extra:
            chat_tool: Name of the chat tool (default: "chat")
            completion_tool: Name of completion tool (default: "completion")
            use_sse: Use Server-Sent Events for streaming (default: True)
    """
    
    @property
    def name(self) -> str:
        return "mcp"
    
    @property
    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_streaming=True,
            supports_threads=True,
            supports_tools=True,
            supports_vision=False,  # Depends on underlying model
            supports_files=False,
            supports_system_prompt=True,
            supports_message_history=True,
            max_context_tokens=128000,
            supports_structured_output=True,
            supports_function_calling=True,
        )
    
    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
        self._chat_tool = config.extra.get("chat_tool", "chat")
        self._completion_tool = config.extra.get("completion_tool", "completion")
        self._use_sse = config.extra.get("use_sse", True)
        self._available_tools: list[dict] = []
        self._available_resources: list[dict] = []
    
    async def initialize(self) -> None:
        """Initialize the MCP client and discover capabilities."""
        if not self.config.api_url:
            logger.warning("mcp_no_api_url")
            return
        
        self._client = httpx.AsyncClient(
            base_url=self.config.api_url,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        
        # Discover available tools
        try:
            await self._discover_capabilities()
            self._initialized = True
            logger.info(
                "mcp_backend_initialized",
                url=self.config.api_url,
                tools=len(self._available_tools),
                resources=len(self._available_resources),
            )
        except Exception as e:
            logger.error("mcp_initialization_failed", error=str(e))
            self._initialized = True  # Mark as initialized, will retry
    
    async def _discover_capabilities(self) -> None:
        """Discover available MCP tools and resources."""
        # List tools
        try:
            response = await self._client.post("/tools/list", json={})
            if response.status_code == 200:
                data = response.json()
                self._available_tools = data.get("tools", [])
                logger.debug("mcp_tools_discovered", count=len(self._available_tools))
        except Exception as e:
            logger.warning("mcp_tools_list_failed", error=str(e))
        
        # List resources
        try:
            response = await self._client.post("/resources/list", json={})
            if response.status_code == 200:
                data = response.json()
                self._available_resources = data.get("resources", [])
                logger.debug("mcp_resources_discovered", count=len(self._available_resources))
        except Exception as e:
            logger.warning("mcp_resources_list_failed", error=str(e))
    
    async def shutdown(self) -> None:
        """Shutdown the client."""
        if self._client:
            await self._client.aclose()
        self._initialized = False
        logger.info("mcp_backend_shutdown")
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a message via MCP chat tool."""
        if not self._client:
            return ChatResponse(
                content="⚠️ MCP backend not initialized.",
                thread_id=request.thread_id or "error",
            )
        
        # Build the tool call
        arguments = {
            "message": request.message,
        }
        
        if request.thread_id:
            arguments["thread_id"] = request.thread_id
        
        if request.message_history:
            arguments["history"] = request.message_history
        
        if request.system_prompt or self.config.system_prompt:
            arguments["system_prompt"] = request.system_prompt or self.config.system_prompt
        
        try:
            response = await self._call_tool(self._chat_tool, arguments)
            
            # Parse response
            content = response.get("content", "")
            if isinstance(content, list):
                # MCP content blocks
                texts = [
                    block.get("text", "")
                    for block in content
                    if block.get("type") == "text"
                ]
                content = "\n".join(texts)
            
            return ChatResponse(
                content=content or "No response from MCP server.",
                thread_id=response.get("thread_id", request.thread_id or "mcp"),
                model=response.get("model"),
                tokens_used=response.get("tokens_used"),
                tool_calls=response.get("tool_calls"),
                raw_response=response,
            )
            
        except Exception as e:
            logger.error("mcp_chat_failed", error=str(e))
            return ChatResponse(
                content=f"⚠️ MCP communication error: {e}",
                thread_id=request.thread_id or "error",
            )
    
    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Stream a response via MCP."""
        if not self._client or not self._use_sse:
            response = await self.chat(request)
            yield response.content
            return
        
        arguments = {
            "message": request.message,
            "stream": True,
        }
        
        if request.thread_id:
            arguments["thread_id"] = request.thread_id
        
        try:
            async with self._client.stream(
                "POST",
                "/tools/call",
                json={
                    "name": self._chat_tool,
                    "arguments": arguments,
                },
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            if chunk.get("content"):
                                yield chunk["content"]
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error("mcp_stream_failed", error=str(e))
            yield f"⚠️ MCP streaming error: {e}"
    
    async def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool."""
        response = await self._client.post(
            "/tools/call",
            json={
                "name": tool_name,
                "arguments": arguments,
            },
        )
        response.raise_for_status()
        return response.json()
    
    async def _read_resource(self, uri: str) -> dict:
        """Read an MCP resource."""
        response = await self._client.post(
            "/resources/read",
            json={"uri": uri},
        )
        response.raise_for_status()
        return response.json()
    
    async def get_wisdom(self) -> str:
        """Get wisdom via MCP (if available)."""
        # Check if there's a wisdom tool
        wisdom_tools = [t for t in self._available_tools if "wisdom" in t.get("name", "").lower()]
        
        if wisdom_tools:
            try:
                result = await self._call_tool(wisdom_tools[0]["name"], {})
                content = result.get("content", "")
                if isinstance(content, list):
                    content = "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
                return content or "The MCP server offers no wisdom today."
            except Exception:
                pass
        
        return "📜 _The MCP bridge carries messages, but wisdom must be sought elsewhere._"
    
    def get_available_tools(self) -> list[dict]:
        """Get the list of available MCP tools."""
        return self._available_tools
    
    def get_available_resources(self) -> list[dict]:
        """Get the list of available MCP resources."""
        return self._available_resources


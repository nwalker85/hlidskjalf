"""
Norns Backend — Integration with the Hliðskjálf Norns AI System.

The Norns are three sisters who sit at the Well of Urðr:
- Urðr (Urd): "That which has become" — analyzes the past
- Verðandi: "That which is happening" — observes the present
- Skuld: "That which shall be" — predicts and plans the future
"""

from typing import AsyncIterator, Optional

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


@register_backend("norns")
class NornsBackend(BaseBackend):
    """
    Backend for the Norns AI system.
    
    Supports both direct Hlidskjalf API and LangGraph API.
    """
    
    @property
    def name(self) -> str:
        return "norns"
    
    @property
    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_streaming=True,
            supports_threads=True,
            supports_tools=True,
            supports_vision=False,
            supports_files=False,
            supports_system_prompt=True,
            supports_message_history=True,
            max_context_tokens=128000,
            supports_structured_output=False,
            supports_function_calling=True,
        )
    
    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._client: Optional[httpx.AsyncClient] = None
        self._use_langgraph = config.extra.get("use_langgraph", True)
    
    async def initialize(self) -> None:
        """Initialize the Norns client."""
        if not self.config.api_url:
            logger.warning("norns_no_api_url")
            return
        
        self._client = httpx.AsyncClient(
            base_url=self.config.api_url,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
        
        # Test connection
        try:
            if self._use_langgraph:
                response = await self._client.get("/info")
            else:
                response = await self._client.get("/health")
            response.raise_for_status()
            self._initialized = True
            logger.info("norns_backend_initialized", url=self.config.api_url)
        except Exception as e:
            logger.warning("norns_connection_test_failed", error=str(e))
            self._initialized = True  # Still mark as initialized, will retry on requests
    
    async def shutdown(self) -> None:
        """Shutdown the client."""
        if self._client:
            await self._client.aclose()
        self._initialized = False
        logger.info("norns_backend_shutdown")
    
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a message to the Norns."""
        if not self._client:
            return ChatResponse(
                content="⚠️ Norns backend not initialized.",
                thread_id=request.thread_id or "error",
                current_norn="verdandi",
            )
        
        if self._use_langgraph:
            return await self._chat_langgraph(request)
        else:
            return await self._chat_direct(request)
    
    async def _chat_direct(self, request: ChatRequest) -> ChatResponse:
        """Chat via the direct Hlidskjalf API."""
        payload = {"message": request.message}
        if request.thread_id:
            payload["thread_id"] = request.thread_id
        
        try:
            response = await self._client.post("/norns/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            
            return ChatResponse(
                content=data.get("response", "The Norns are silent..."),
                thread_id=data.get("thread_id", request.thread_id or "unknown"),
                current_norn=data.get("current_norn", "verdandi"),
            )
        except httpx.HTTPStatusError as e:
            logger.error("norns_api_error", status=e.response.status_code)
            return ChatResponse(
                content=f"⚠️ The threads of fate are tangled: {e.response.status_code}",
                thread_id=request.thread_id or "error",
                current_norn="verdandi",
            )
        except Exception as e:
            logger.error("norns_connection_error", error=str(e))
            return ChatResponse(
                content="⚠️ Cannot reach the Well of Urðr...",
                thread_id=request.thread_id or "error",
                current_norn="verdandi",
            )
    
    async def _chat_langgraph(self, request: ChatRequest) -> ChatResponse:
        """Chat via the LangGraph API."""
        thread_id = request.thread_id
        
        # Create thread if needed
        if not thread_id:
            try:
                thread_resp = await self._client.post("/threads", json={})
                if thread_resp.status_code == 200:
                    thread_data = thread_resp.json()
                    thread_id = thread_data.get("thread_id")
            except Exception as e:
                logger.warning("failed_to_create_thread", error=str(e))
                thread_id = f"bifrost-{id(request.message)}"
        
        # Create a run
        payload = {
            "assistant_id": "norns",
            "input": {
                "messages": [{"role": "user", "content": request.message}]
            },
            "config": {
                "configurable": {"thread_id": thread_id}
            },
        }
        
        try:
            response = await self._client.post(
                f"/threads/{thread_id}/runs/wait",
                json=payload,
            )
            
            if response.status_code == 404:
                await self._client.post("/threads", json={"thread_id": thread_id})
                response = await self._client.post(
                    f"/threads/{thread_id}/runs/wait",
                    json=payload,
                )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract AI response
            messages = data.get("messages", [])
            ai_response = "The Norns are silent..."
            
            for msg in reversed(messages):
                if msg.get("type") == "ai" or msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    if isinstance(content, str) and content:
                        ai_response = content
                        break
                    elif isinstance(content, list):
                        texts = [
                            b.get("text", "") 
                            for b in content 
                            if isinstance(b, dict) and b.get("type") == "text"
                        ]
                        if texts:
                            ai_response = " ".join(texts)
                            break
            
            return ChatResponse(
                content=ai_response,
                thread_id=thread_id,
                current_norn=self.detect_response_persona(ai_response),
            )
            
        except httpx.HTTPStatusError as e:
            logger.error("langgraph_api_error", status=e.response.status_code)
            return ChatResponse(
                content=f"⚠️ The threads of fate are tangled: {e.response.status_code}",
                thread_id=thread_id or "error",
                current_norn="verdandi",
            )
        except Exception as e:
            logger.error("langgraph_connection_error", error=str(e))
            return ChatResponse(
                content="⚠️ Cannot reach the Well of Urðr...",
                thread_id=thread_id or "error",
                current_norn="verdandi",
            )
    
    async def get_wisdom(self) -> str:
        """Get wisdom from the Norns."""
        if not self._client:
            return "📜 _The bridge to Urðr's Well is not yet built._"
        
        try:
            response = await self._client.get("/norns/wisdom")
            response.raise_for_status()
            data = response.json()
            wisdom = data.get("wisdom", "The Well reflects only silence today.")
            source = data.get("from", "The Norns")
            return f"📜 *{source}*:\n_{wisdom}_"
        except Exception as e:
            logger.warning("wisdom_fetch_failed", error=str(e))
            return "📜 _The threads are tangled; wisdom cannot flow today._"
    
    def detect_response_persona(self, content: str) -> str:
        """Detect which Norn is primarily speaking."""
        lower = content.lower()
        if any(word in lower for word in ["urðr", "urdr", "past", "history", "was"]):
            return "urd"
        if any(word in lower for word in ["skuld", "future", "shall", "plan", "will be"]):
            return "skuld"
        return "verdandi"


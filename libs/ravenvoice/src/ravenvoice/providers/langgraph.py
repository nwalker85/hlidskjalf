"""
LangGraph Brain Provider — AI Agent via LangGraph API.

Connects to a LangGraph server (like the Norns) for conversational AI.
"""

from typing import AsyncIterator, Optional

import httpx
import structlog

from ravenvoice.providers.base import BaseBrain, BrainResponse

logger = structlog.get_logger(__name__)


class LangGraphBrain(BaseBrain):
    """
    LangGraph AI Brain provider.
    
    Connects to a LangGraph server to handle conversational AI.
    Perfect for connecting to the Norns or any LangGraph-based agent.
    
    Configuration:
        brain = LangGraphBrain(
            api_url="http://langgraph:2024",
            assistant_id="norns",
        )
    """
    
    def __init__(
        self,
        api_url: str = "http://localhost:2024",
        assistant_id: str = "norns",
        timeout: float = 120.0,
    ):
        """
        Initialize LangGraph Brain.
        
        Args:
            api_url: LangGraph server URL
            assistant_id: Assistant/graph ID to use
            timeout: Request timeout in seconds
        """
        self._api_url = api_url.rstrip("/")
        self._assistant_id = assistant_id
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "langgraph"
    
    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self._api_url,
            timeout=httpx.Timeout(self._timeout, connect=10.0),
        )
        logger.info("langgraph_brain_initialized", url=self._api_url, assistant=self._assistant_id)
    
    async def shutdown(self) -> None:
        """Cleanup."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def think(
        self,
        text: str,
        thread_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> BrainResponse:
        """Send message to LangGraph and get response."""
        if self._client is None:
            await self.initialize()
        
        # Create thread if needed
        if not thread_id:
            try:
                resp = await self._client.post("/threads", json={})
                if resp.status_code == 200:
                    thread_id = resp.json().get("thread_id")
            except Exception as e:
                logger.warning("failed_to_create_thread", error=str(e))
                thread_id = f"voice-{id(text)}"
        
        # Build run request
        payload = {
            "assistant_id": self._assistant_id,
            "input": {
                "messages": [{"role": "user", "content": text}]
            },
            "config": {
                "configurable": {"thread_id": thread_id}
            },
        }
        
        # Add context if provided
        if context:
            payload["input"]["context"] = context
        
        try:
            response = await self._client.post(
                f"/threads/{thread_id}/runs/wait",
                json=payload,
            )
            
            if response.status_code == 404:
                # Thread doesn't exist, create and retry
                await self._client.post("/threads", json={"thread_id": thread_id})
                response = await self._client.post(
                    f"/threads/{thread_id}/runs/wait",
                    json=payload,
                )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract AI response
            messages = data.get("messages", [])
            ai_text = ""
            tool_calls = []
            
            for msg in reversed(messages):
                if msg.get("type") == "ai" or msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    if isinstance(content, str) and content:
                        ai_text = content
                        break
                    elif isinstance(content, list):
                        texts = [
                            b.get("text", "")
                            for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        ]
                        if texts:
                            ai_text = " ".join(texts)
                            break
                    
                    # Capture tool calls
                    if msg.get("tool_calls"):
                        tool_calls = msg["tool_calls"]
            
            # Detect persona (for Norns-style responses)
            persona = self._detect_persona(ai_text)
            
            return BrainResponse(
                text=ai_text or "...",
                thread_id=thread_id,
                persona=persona,
                tool_calls=tool_calls if tool_calls else None,
                provider=self.name,
            )
            
        except httpx.HTTPStatusError as e:
            logger.error("langgraph_api_error", status=e.response.status_code)
            return BrainResponse(
                text="I'm having trouble thinking right now.",
                thread_id=thread_id,
                provider=self.name,
            )
        except Exception as e:
            logger.error("langgraph_error", error=str(e))
            return BrainResponse(
                text="My connection to the Well of Urðr has been disrupted.",
                thread_id=thread_id,
                provider=self.name,
            )
    
    async def think_stream(
        self,
        text: str,
        thread_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AsyncIterator[str]:
        """Stream response from LangGraph."""
        if self._client is None:
            await self.initialize()
        
        # Create thread if needed
        if not thread_id:
            try:
                resp = await self._client.post("/threads", json={})
                if resp.status_code == 200:
                    thread_id = resp.json().get("thread_id")
            except Exception:
                thread_id = f"voice-{id(text)}"
        
        payload = {
            "assistant_id": self._assistant_id,
            "input": {
                "messages": [{"role": "user", "content": text}]
            },
            "config": {
                "configurable": {"thread_id": thread_id}
            },
            "stream_mode": ["messages"],
        }
        
        if context:
            payload["input"]["context"] = context
        
        try:
            async with self._client.stream(
                "POST",
                f"/threads/{thread_id}/runs/stream",
                json=payload,
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json
                        try:
                            data = json.loads(line[6:])
                            if isinstance(data, dict):
                                content = data.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error("langgraph_stream_error", error=str(e))
            yield "I'm having trouble responding."
    
    def _detect_persona(self, text: str) -> str:
        """Detect persona from response (for Norns-style agents)."""
        lower = text.lower()
        if any(word in lower for word in ["urðr", "urdr", "past", "history", "was"]):
            return "urd"
        if any(word in lower for word in ["skuld", "future", "shall", "plan", "will be"]):
            return "skuld"
        return "verdandi"


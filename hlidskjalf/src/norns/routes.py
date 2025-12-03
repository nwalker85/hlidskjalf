"""
API routes for conversing with the Norns
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.norns.agent import NornsAgent

router = APIRouter(prefix="/norns", tags=["Norns"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ChatRequest(BaseModel):
    """Request to chat with the Norns"""
    message: str = Field(..., description="Your message to the Norns")
    thread_id: Optional[str] = Field(
        None,
        description="Thread ID for conversation continuity. Omit to start new conversation."
    )


class ChatResponse(BaseModel):
    """Response from the Norns"""
    response: str = Field(..., description="The Norns' response")
    thread_id: str = Field(..., description="Thread ID for continuing the conversation")
    current_norn: str = Field(..., description="Which Norn is primarily speaking (urd/verdandi/skuld)")


# =============================================================================
# ROUTES
# =============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat_with_norns(
    request: ChatRequest,
    # session: AsyncSession = Depends(get_session)  # Uncomment when integrated
):
    """
    Consult the Norns — the three sisters who weave fate.
    
    The Norns will help you:
    - **Observe** the current state of your realms (Verðandi)
    - **Analyze** past events and logs (Urðr)
    - **Plan** future deployments and changes (Skuld)
    
    They can use their tools to:
    - Check project status and health
    - Analyze logs and deployment history
    - Allocate ports for new services
    - Generate nginx configurations
    - Plan deployments across realms
    - Predict potential issues
    
    Example messages:
    - "What is the status of the SAAA project?"
    - "Why did deployments fail yesterday?"
    - "Help me deploy ravenmaskos to staging"
    - "What ports are available?"
    - "Predict any issues I should know about"
    """
    try:
        agent = NornsAgent()
        thread_ref = request.thread_id or agent.thread_id
        response = await agent.chat(message=request.message, thread_id=thread_ref)
        current_norn = "verdandi"
        response_lower = response.lower()
        if any(keyword in response_lower for keyword in ["urðr", "urdr", "past", "history"]):
            current_norn = "urd"
        elif any(keyword in response_lower for keyword in ["skuld", "future", "shall", "plan"]):
            current_norn = "skuld"
        return ChatResponse(response=response, thread_id=thread_ref, current_norn=current_norn)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"The Norns encountered an error in the threads of fate: {exc}",
        ) from exc


@router.post("/chat/stream")
async def stream_chat_with_norns(
    request: ChatRequest,
):
    """
    Stream a conversation with the Norns.
    
    Returns a Server-Sent Events stream of the Norns' response,
    allowing for real-time display as they speak.
    """
    async def generate():
        agent = NornsAgent()
        thread_ref = request.thread_id or agent.thread_id
        async for chunk in agent.stream(message=request.message, thread_id=thread_ref):
            yield f"data: {chunk}\n\n"
        yield f'data: {{"thread_id": "{thread_ref}"}}\n\n'
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/wisdom")
async def get_norn_wisdom():
    """
    Receive wisdom from the Norns.
    
    Returns a random piece of wisdom about the Nine Realms.
    """
    import random
    
    wisdom = [
        "The threads of fate are woven not in isolation, but in the tapestry of all things connected.",
        "What was, what is, and what shall be — all are one in the Well of Urðr.",
        "Even Odin, from his high seat, cannot see all ends. Trust in the weaving.",
        "Midgard is where mortals build, but Asgard is where their work becomes eternal.",
        "A deployment without tests is like a ship without oars — it may float, but it will not steer.",
        "The healthiest service is one that knows when it is sick.",
        "Ports are like doorways — assign them wisely, for traffic flows through them.",
        "Logs are the memory of machines. Ignore them, and you ignore your own history.",
        "Scaling up is easy. Scaling wisely is the work of the Norns.",
        "The best rollback is the one you never need.",
    ]
    
    return {
        "wisdom": random.choice(wisdom),
        "from": random.choice(["Urðr", "Verðandi", "Skuld"])
    }


@router.get("/graph")
async def get_norn_graph_info():
    """
    Provide the LangGraph metadata required by the Agent Chat UI.
    """
    settings = get_settings()
    return {
        "graph_id": settings.APP_NAME.lower().replace(" ", "-"),
        "model": settings.NORNS_MODEL,
        "api_url": settings.NORNS_GRAPH_API_URL,
        "assistant_id": settings.NORNS_GRAPH_ASSISTANT_ID,
    }


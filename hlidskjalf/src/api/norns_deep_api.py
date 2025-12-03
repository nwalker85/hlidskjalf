"""
API Endpoints for Norns Deep Agent with Specialized Subagents

Provides chat interface and streaming capabilities for the frontend.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
import json

from src.norns.deep_agent import create_norns_deep_agent, get_subagent_catalog

router = APIRouter(prefix="/api/v1/norns", tags=["norns"])


class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    current_norn: str
    subagents_used: list[str] = []
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_norns(request: ChatRequest):
    """
    Chat with the Norns deep agent.
    The Norns will delegate to specialized subagents as needed.
    """
    try:
        # Create deep agent (cached in production)
        agent = create_norns_deep_agent()
        
        # Execute
        result = await agent.ainvoke({
            "messages": [("user", request.message)]
        })
        
        # Extract response
        messages = result.get("messages", [])
        if not messages:
            raise HTTPException(500, "No response from agent")
        
        final_message = messages[-1].content
        
        # Determine which Norn is speaking (simple heuristic)
        content_lower = final_message.lower()
        if any(word in content_lower for word in ["past", "history", "urðr", "recall"]):
            current_norn = "urd"
        elif any(word in content_lower for word in ["future", "plan", "shall", "skuld"]):
            current_norn = "skuld"
        else:
            current_norn = "verdandi"
        
        # Extract subagents used (if available in metadata)
        subagents_used = []
        # TODO: Track which subagents were invoked
        
        return ChatResponse(
            response=final_message,
            thread_id=request.thread_id or "thread-001",
            current_norn=current_norn,
            subagents_used=subagents_used
        )
        
    except Exception as e:
        raise HTTPException(500, f"Agent error: {str(e)}")


@router.get("/stream")
async def stream_norns_chat(message: str, thread_id: Optional[str] = None):
    """
    Stream response from Norns for real-time UI updates.
    Server-Sent Events (SSE) format.
    """
    
    async def event_stream():
        try:
            agent = create_norns_deep_agent()
            
            # Stream token by token
            async for event in agent.astream_events(
                {"messages": [("user", message)]},
                version="v2"
            ):
                # Stream Claude's tokens
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, 'content') and chunk.content:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"
                
                # Stream subagent invocations
                elif event["event"] == "on_chain_start":
                    if "name" in event.get("data", {}):
                        agent_name = event["data"]["name"]
                        if agent_name != "Norns":  # It's a subagent!
                            yield f"data: {json.dumps({'type': 'subagent_start', 'agent': agent_name})}\n\n"
                
                elif event["event"] == "on_chain_end":
                    if "name" in event.get("data", {}):
                        agent_name = event["data"]["name"]
                        if agent_name != "Norns":
                            yield f"data: {json.dumps({'type': 'subagent_end', 'agent': agent_name})}\n\n"
            
            # Send completion
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/subagents")
async def list_subagents():
    """
    List all available specialized subagents.
    Useful for UI to show available specialists.
    """
    catalog = get_subagent_catalog()
    
    return {
        "count": len(catalog),
        "subagents": [
            {
                "name": name,
                "description": desc,
                "status": "ready"
            }
            for name, desc in catalog.items()
        ]
    }


@router.get("/observability/stream")
async def stream_agent_logs():
    """
    Stream real-time logs from ALL agents via the observability agent.
    
    This endpoint subscribes to Kafka topics and streams coordination events
    to the frontend for real-time monitoring.
    """
    
    async def log_stream():
        """Stream Kafka events to frontend"""
        try:
            # Import Kafka consumer
            from aiokafka import AIOKafkaConsumer
            from src.norns.squad_schema import Topics
            
            # Subscribe to all coordination topics
            consumer = AIOKafkaConsumer(
                Topics.SQUAD_COORDINATION,
                Topics.TASK_STATUS,
                Topics.HEALTH_STATUS,
                bootstrap_servers="redpanda:9092",  # Docker service name
                group_id="observability-stream",
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest'
            )
            
            await consumer.start()
            
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Observing agent swarm...'})}\n\n"
            
            try:
                async for msg in consumer:
                    event = msg.value
                    
                    # Format for frontend
                    log_entry = {
                        'type': 'event',
                        'event_type': event.get('event_type'),
                        'source': event.get('source_agent'),
                        'target': event.get('target_agent'),
                        'timestamp': event.get('timestamp'),
                        'payload': event.get('payload', {})
                    }
                    
                    yield f"data: {json.dumps(log_entry)}\n\n"
                    
            finally:
                await consumer.stop()
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        log_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/status")
async def get_norns_status():
    """
    Get current status of the Norns and all subagents.
    """
    catalog = get_subagent_catalog()
    
    # Check Kafka/NATS connectivity
    import subprocess
    
    kafka_status = "unknown"
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "redpanda"],
            capture_output=True,
            text=True,
            timeout=5
        )
        kafka_status = "healthy" if "healthy" in result.stdout else "unhealthy"
    except:
        kafka_status = "unavailable"
    
    nats_status = "unknown"
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "nats"],
            capture_output=True,
            text=True,
            timeout=5
        )
        nats_status = "running" if "Up" in result.stdout else "down"
    except:
        nats_status = "unavailable"
    
    return {
        "norns_status": "operational",
        "main_model": "claude-sonnet-4-20250514",
        "subagent_count": len(catalog),
        "event_bus": {
            "kafka": kafka_status,
            "nats": nats_status
        },
        "capabilities": list(catalog.keys())
    }


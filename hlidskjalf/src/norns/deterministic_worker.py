"""
React Worker Agents

These agents use LangGraph's create_react_agent to handle tool execution loops.
The Claude orchestrator does high-level reasoning, workers execute with tools.
"""

import asyncio
import json
from typing import Optional, Any
from uuid import uuid4
from datetime import datetime

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from src.norns.squad_schema import (
    AgentRole,
    AgentEvent,
    EventType,
    TaskAssignment,
    Topics,
    AGENT_PROMPTS,
)
from src.norns.tools import workspace_read, workspace_write, execute_terminal_command


class ReactWorker:
    """
    A worker agent that uses create_react_agent for tool execution.
    Uses Ollama for local, fast execution without rate limits.
    """
    
    def __init__(
        self,
        role: AgentRole,
        kafka_bootstrap: str = "redpanda:9092",  # Docker service name
        use_ollama: bool = True
    ):
        self.role = role
        self.kafka_bootstrap = kafka_bootstrap
        self.use_ollama = use_ollama
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.running = False
        self.tasks_completed = []
        self.agent_executor = None
        
    async def connect(self):
        """Connect to Redpanda"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_bootstrap,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        
        topics = [Topics.SQUAD_COORDINATION, Topics.TASK_STATUS]
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.kafka_bootstrap,
            group_id=f"worker-{self.role.value}",
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest'  # Get all messages including historical ones
        )
        await self.consumer.start()
        
        # Create ReAct agent with tools
        if self.use_ollama:
            llm = ChatOllama(model="llama3.1:latest", temperature=0)
        else:
            llm = ChatAnthropic(model="claude-3-5-haiku-20241022", temperature=0)
            
        # Create react agent - handles tool execution loop automatically!
        self.agent_executor = create_react_agent(
            llm,
            tools=[workspace_read, workspace_write, execute_terminal_command]
        )
        
        print(f"✓ {self.role.value} worker ready and listening")
        
    async def disconnect(self):
        """Disconnect from Redpanda"""
        if self.producer:
            await self.producer.stop()
        if self.consumer:
            await self.consumer.stop()
            
    async def emit_event(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        correlation_id: Optional[str] = None
    ):
        """Emit an event"""
        event = AgentEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            source_agent=self.role,
            timestamp=datetime.utcnow(),
            correlation_id=correlation_id,
            payload=payload
        )
        
        await self.producer.send_and_wait(
            Topics.SQUAD_COORDINATION,
            value=event.model_dump(mode='json')
        )
        
    async def execute_task(self, task: TaskAssignment) -> dict:
        """Execute task using ReAct agent with tools"""
        print(f"      {self.role.value}: Executing task with ReAct agent...")
        
        try:
            # Get role-specific prompt
            role_prompt = AGENT_PROMPTS.get(self.role, f"You are {self.role.value}")
            
            # Build task message with role context
            task_message = f"""{role_prompt}

Task ID: {task.task_id}
Task Description: {task.description}
Parameters: {json.dumps(task.parameters, indent=2)}

Execute this task step-by-step using the available tools:
- execute_terminal_command: Run shell/docker commands
- workspace_read: Read files
- workspace_write: Create/modify files

Report what you did and the result."""
            
            # Use create_react_agent - it handles the entire tool loop!
            result = await self.agent_executor.ainvoke(
                {"messages": [("user", task_message)]}
            )
            
            # Extract final AI message
            final_message = result["messages"][-1].content if result["messages"] else "No response"
            
            return {
                "status": "completed",
                "result": final_message,
                "tool_calls_made": len([m for m in result["messages"] if hasattr(m, 'tool_calls') and m.tool_calls])
            }
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
            
    async def run(self):
        """Main worker loop"""
        self.running = True
        print(f"      {self.role.value}: Starting message consumption...")
        msg_count = 0
        
        try:
            async for msg in self.consumer:
                msg_count += 1
                
                if not self.running:
                    print(f"      {self.role.value}: Stopping (received {msg_count} messages)")
                    break
                
                event_data = msg.value
                event = AgentEvent(**event_data)
                
                # Only process TASK_ASSIGNED events for our role
                if event.event_type != EventType.TASK_ASSIGNED:
                    continue
                    
                if event.target_agent != self.role:
                    continue
                
                print(f"      {self.role.value}: 🎯 RECEIVED TASK: {event.payload.get('task_id')}")
                    
                if event.event_type == EventType.TASK_ASSIGNED:
                    task = TaskAssignment(**event.payload)
                    
                    # Emit started
                    await self.emit_event(
                        EventType.TASK_STARTED,
                        {"task_id": task.task_id},
                        correlation_id=event.correlation_id
                    )
                    
                    # Execute
                    result = await self.execute_task(task)
                    
                    # Emit result
                    if result.get("status") == "completed":
                        await self.emit_event(
                            EventType.TASK_COMPLETED,
                            {"task_id": task.task_id, "result": result.get("result")},
                            correlation_id=event.correlation_id
                        )
                        self.tasks_completed.append(task.task_id)
                        print(f"      ✓ {self.role.value}: Task complete")
                    else:
                        await self.emit_event(
                            EventType.TASK_FAILED,
                            {"task_id": task.task_id, "error": result.get("error")},
                            correlation_id=event.correlation_id
                        )
                        print(f"      ✗ {self.role.value}: Task failed - {result.get('error', '')[:50]}")
                        
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False


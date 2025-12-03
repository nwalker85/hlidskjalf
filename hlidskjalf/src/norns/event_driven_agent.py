"""
Event-Driven Norns Agent System

Uses Redpanda/Kafka for agent coordination instead of LangChain message history.
This completely sidesteps OpenAI API message ordering constraints.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Optional, Any
from uuid import uuid4

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

from src.core.config import get_settings
from src.norns.squad_schema import (
    AgentRole,
    AgentEvent,
    EventType,
    TaskAssignment,
    TaskProgress,
    ServiceStatus,
    Topics,
    AGENT_PROMPTS,
    DEPLOYMENT_ORDER,
)


class EventDrivenAgent:
    """
    An agent that communicates via Redpanda events instead of LangChain messages.
    Completely avoids OpenAI API message ordering issues.
    """
    
    def __init__(
        self,
        role: AgentRole,
        kafka_bootstrap: str = "redpanda:9092",  # Docker service name
        model: str = "gpt-4o",
        use_ollama: bool = True
    ):
        self.role = role
        self.kafka_bootstrap = kafka_bootstrap
        self.model = model
        self.use_ollama = use_ollama
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.running = False
        self.tasks_completed = []
        
    async def connect(self):
        """Connect to Redpanda"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_bootstrap,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        
        # Subscribe to relevant topics
        topics = [Topics.SQUAD_COORDINATION, Topics.TASK_STATUS]
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.kafka_bootstrap,
            group_id=f"agent-{self.role.value}",
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest'
        )
        await self.consumer.start()
        print(f"✓ {self.role.value} connected to Redpanda")
        
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
        target_agent: Optional[AgentRole] = None,
        correlation_id: Optional[str] = None
    ):
        """Emit an event to Redpanda"""
        event = AgentEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            source_agent=self.role,
            target_agent=target_agent,
            timestamp=datetime.utcnow(),
            correlation_id=correlation_id,
            payload=payload
        )
        
        await self.producer.send_and_wait(
            Topics.SQUAD_COORDINATION,
            value=event.model_dump(mode='json')
        )
        
    async def execute_task(self, task: TaskAssignment) -> dict:
        """
        Execute a task using LLM + tools WITHOUT message history.
        Makes a single LLM call with task context.
        """
        # Use Ollama for local execution (no rate limits!)
        if self.use_ollama:
            llm = ChatOllama(model="llama3.1:latest", temperature=0.2)
        else:
            llm = ChatOpenAI(model=self.model, temperature=0.2)
        
        # Get agent-specific prompt
        agent_prompt = AGENT_PROMPTS.get(self.role, "You are a specialist agent.")
        
        # Create a single-shot prompt (no conversation history needed!)
        messages = [
            SystemMessage(content=f"""{agent_prompt}

You have access to tools: workspace_read, workspace_write, execute_terminal_command.

Task: {task.description}
Parameters: {json.dumps(task.parameters, indent=2)}

Execute the task step-by-step. Return a JSON report with:
{{
  "status": "completed" or "failed",
  "actions_taken": ["action 1", "action 2", ...],
  "result": "summary of outcome",
  "next_steps": ["optional recommendations"]
}}
"""),
            HumanMessage(content=f"Execute task {task.task_id}: {task.description}")
        ]
        
        # Bind tools
        from src.norns.tools import workspace_read, workspace_write, execute_terminal_command
        llm_with_tools = llm.bind_tools([workspace_read, workspace_write, execute_terminal_command])
        
        try:
            # Single invocation - no conversation history!
            response = await llm_with_tools.ainvoke(messages)
            
            # Handle tool calls if any
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_messages = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    tool_call_id = tool_call['id']
                    
                    # Execute tool
                    try:
                        if tool_name == 'workspace_read':
                            result = await workspace_read.ainvoke(tool_args)
                        elif tool_name == 'workspace_write':
                            result = await workspace_write.ainvoke(tool_args)
                        elif tool_name == 'execute_terminal_command':
                            result = await execute_terminal_command.ainvoke(tool_args)
                        else:
                            result = {"error": f"Unknown tool: {tool_name}"}
                    except Exception as e:
                        result = {"error": str(e)}
                    
                    # Create proper ToolMessage
                    tool_msg = ToolMessage(
                        content=json.dumps(result),
                        tool_call_id=tool_call_id,
                        name=tool_name
                    )
                    tool_messages.append(tool_msg)
                
                # Make one more call with proper message sequence
                # Messages: [System, Human, AI(with tool_calls), Tool1, Tool2, ...]
                final_response = await llm.ainvoke(messages + [response] + tool_messages)
                return {"status": "completed", "result": final_response.content}
            
            return {"status": "completed", "result": response.content}
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
            
    async def run(self):
        """Main agent loop - listen for events and execute tasks"""
        self.running = True
        print(f"🎯 {self.role.value} agent running...")
        
        try:
            async for msg in self.consumer:
                if not self.running:
                    break
                    
                event_data = msg.value
                event = AgentEvent(**event_data)
                
                # Ignore our own events
                if event.source_agent == self.role:
                    continue
                
                # Handle task assignments
                if event.event_type == EventType.TASK_ASSIGNED:
                    task = TaskAssignment(**event.payload)
                    print(f"  {self.role.value} received task: {task.task_id}")
                    
                    # Emit started event
                    await self.emit_event(
                        EventType.TASK_STARTED,
                        {"task_id": task.task_id},
                        correlation_id=event.correlation_id
                    )
                    
                    # Execute task
                    result = await self.execute_task(task)
                    
                    # Emit completion/failure event
                    if result.get("status") == "completed":
                        await self.emit_event(
                            EventType.TASK_COMPLETED,
                            {
                                "task_id": task.task_id,
                                "result": result.get("result", "")
                            },
                            correlation_id=event.correlation_id
                        )
                        self.tasks_completed.append(task.task_id)
                        print(f"  ✓ {self.role.value} completed: {task.task_id}")
                    else:
                        await self.emit_event(
                            EventType.TASK_FAILED,
                            {
                                "task_id": task.task_id,
                                "error": result.get("error", "Unknown error")
                            },
                            correlation_id=event.correlation_id
                        )
                        print(f"  ✗ {self.role.value} failed: {task.task_id}")
                        
        except asyncio.CancelledError:
            print(f"  {self.role.value} shutting down...")
        finally:
            self.running = False


class EventDrivenOrchestrator:
    """
    Orchestrates multiple agents via Redpanda events.
    No LangChain message history needed!
    """
    
    def __init__(self, kafka_bootstrap: str = "redpanda:9092"):  # Docker service name
        self.kafka_bootstrap = kafka_bootstrap
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.agents: dict[AgentRole, EventDrivenAgent] = {}
        self.agent_tasks: dict[AgentRole, asyncio.Task] = {}
        self.completed_tasks: set[str] = set()
        self.failed_tasks: set[str] = set()
        
    async def connect(self):
        """Connect orchestrator to Redpanda"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_bootstrap,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        
        self.consumer = AIOKafkaConsumer(
            Topics.SQUAD_COORDINATION,
            Topics.TASK_STATUS,
            Topics.HEALTH_STATUS,
            bootstrap_servers=self.kafka_bootstrap,
            group_id="orchestrator",
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest'
        )
        await self.consumer.start()
        print("✓ Orchestrator connected to Redpanda")
        
    async def spawn_agent(self, role: AgentRole, use_ollama: bool = True):
        """Spawn and start an agent"""
        agent = EventDrivenAgent(role, self.kafka_bootstrap, use_ollama=use_ollama)
        await agent.connect()
        self.agents[role] = agent
        
        # Start agent in background
        task = asyncio.create_task(agent.run())
        self.agent_tasks[role] = task
        
    async def assign_task(
        self,
        agent_role: AgentRole,
        task_id: str,
        description: str,
        parameters: dict[str, Any] = None,
        correlation_id: Optional[str] = None
    ):
        """Assign a task to an agent via Redpanda"""
        task = TaskAssignment(
            task_id=task_id,
            description=description,
            parameters=parameters or {},
            dependencies=[],
            timeout_seconds=300,
            retry_count=0
        )
        
        event = AgentEvent(
            event_id=str(uuid4()),
            event_type=EventType.TASK_ASSIGNED,
            source_agent=AgentRole.ORCHESTRATOR,
            target_agent=agent_role,
            correlation_id=correlation_id or str(uuid4()),
            payload=task.model_dump()
        )
        
        await self.producer.send_and_wait(
            Topics.SQUAD_COORDINATION,
            value=event.model_dump(mode='json')
        )
        print(f"📋 Assigned {task_id} to {agent_role.value}")
        
    async def monitor_events(self, timeout_seconds: int = 300):
        """Monitor events and track task completion"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            async for msg in self.consumer:
                event_data = msg.value
                event = AgentEvent(**event_data)
                
                if event.event_type == EventType.TASK_COMPLETED:
                    task_id = event.payload.get("task_id")
                    self.completed_tasks.add(task_id)
                    print(f"  ✅ Task completed: {task_id} by {event.source_agent.value}")
                    
                elif event.event_type == EventType.TASK_FAILED:
                    task_id = event.payload.get("task_id")
                    self.failed_tasks.add(task_id)
                    error = event.payload.get("error", "Unknown")
                    print(f"  ❌ Task failed: {task_id} - {error}")
                    
                # Check timeout
                if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                    print(f"\n⏱️  Monitoring timeout reached ({timeout_seconds}s)")
                    break
                    
        except asyncio.CancelledError:
            pass
            
    async def shutdown(self):
        """Shutdown all agents and connections"""
        print("\n🛑 Shutting down squad...")
        
        # Stop all agent tasks
        for role, task in self.agent_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        # Disconnect agents
        for agent in self.agents.values():
            await agent.disconnect()
            
        # Disconnect orchestrator
        if self.producer:
            await self.producer.stop()
        if self.consumer:
            await self.consumer.stop()
            
        print("✓ Squad shutdown complete")


async def run_event_driven_deployment():
    """
    Run the Traefik migration using event-driven agents.
    NO MESSAGE HISTORY. Pure event coordination via Redpanda.
    """
    
    print("=" * 80)
    print("🔮 EVENT-DRIVEN MULTI-AGENT DEPLOYMENT")
    print("=" * 80)
    print()
    print("The Norns coordinate via Redpanda events...")
    print()
    
    # Create orchestrator
    orchestrator = EventDrivenOrchestrator()
    await orchestrator.connect()
    
    # Wait a moment for Redpanda to be ready
    await asyncio.sleep(2)
    
    print("=" * 80)
    print("Phase 1: Spawning Agent Squad")
    print("=" * 80)
    print()
    
    # Spawn all agents
    all_roles = [
        AgentRole.CERT_AGENT,
        AgentRole.ENV_AGENT,
        AgentRole.DATABASE_AGENT,
        AgentRole.PROXY_AGENT,
        AgentRole.CACHE_AGENT,
        AgentRole.EVENTS_AGENT,
        AgentRole.SECRETS_AGENT,
        AgentRole.OBSERVABILITY_AGENT,
        AgentRole.DOCKER_AGENT,
        AgentRole.RAG_AGENT,
        AgentRole.GRAPH_AGENT,
        AgentRole.HLIDSKJALF_AGENT,
    ]
    
    for role in all_roles:
        await orchestrator.spawn_agent(role)
        await asyncio.sleep(0.5)
    
    print()
    print("=" * 80)
    print("Phase 2: Executing Deployment in Waves")
    print("=" * 80)
    print()
    
    # Start monitoring in background
    monitor_task = asyncio.create_task(
        orchestrator.monitor_events(timeout_seconds=600)
    )
    
    # Execute deployment order
    correlation_id = str(uuid4())
    
    for wave_num, wave_roles in enumerate(DEPLOYMENT_ORDER, 1):
        print(f"\n🌊 Wave {wave_num}: {', '.join(r.value for r in wave_roles)}")
        print("-" * 80)
        
        # Assign tasks to all agents in this wave
        for role in wave_roles:
            task_id = f"deploy-{role.value}-wave{wave_num}"
            description = AGENT_PROMPTS.get(role, f"Deploy {role.value} services")
            
            await orchestrator.assign_task(
                agent_role=role,
                task_id=task_id,
                description=description,
                parameters={"wave": wave_num},
                correlation_id=correlation_id
            )
        
        # Wait for wave to complete (check every 2 seconds)
        wave_task_ids = {f"deploy-{r.value}-wave{wave_num}" for r in wave_roles}
        timeout = 120  # 2 minutes per wave
        elapsed = 0
        
        while elapsed < timeout:
            await asyncio.sleep(2)
            elapsed += 2
            
            # Check if all tasks in wave completed
            completed = wave_task_ids & orchestrator.completed_tasks
            failed = wave_task_ids & orchestrator.failed_tasks
            
            if completed | failed == wave_task_ids:
                print(f"\n✓ Wave {wave_num} complete: {len(completed)} succeeded, {len(failed)} failed")
                break
                
            # Progress indicator
            if elapsed % 10 == 0:
                done = len(completed) + len(failed)
                total = len(wave_task_ids)
                print(f"  Progress: {done}/{total} tasks...")
        
        if elapsed >= timeout:
            print(f"\n⏱️  Wave {wave_num} timeout - moving to next wave")
    
    print()
    print("=" * 80)
    print("Phase 3: Final Verification")
    print("=" * 80)
    print()
    
    # Give agents a moment to finish
    await asyncio.sleep(5)
    
    # Cancel monitoring
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    
    # Shutdown
    await orchestrator.shutdown()
    
    # Summary
    print()
    print("=" * 80)
    print("📊 DEPLOYMENT SUMMARY")
    print("=" * 80)
    print(f"✅ Tasks completed: {len(orchestrator.completed_tasks)}")
    print(f"❌ Tasks failed: {len(orchestrator.failed_tasks)}")
    print()
    
    if orchestrator.completed_tasks:
        print("Completed tasks:")
        for task_id in sorted(orchestrator.completed_tasks):
            print(f"  ✓ {task_id}")
    
    if orchestrator.failed_tasks:
        print("\nFailed tasks:")
        for task_id in sorted(orchestrator.failed_tasks):
            print(f"  ✗ {task_id}")
    
    print()
    print("=" * 80)
    print("Event-driven deployment complete!")
    print("=" * 80)


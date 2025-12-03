"""
Event-Driven Orchestrator using Claude for Deep Reasoning

The main Norns orchestrator uses Claude (Anthropic) for complex reasoning,
planning, and coordination. Worker agents use Ollama for fast local execution.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Optional, Any
from uuid import uuid4

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage

from src.norns.squad_schema import (
    AgentRole,
    AgentEvent,
    EventType,
    TaskAssignment,
    Topics,
    AGENT_PROMPTS,
    DEPLOYMENT_ORDER,
)
from src.norns.deterministic_worker import ReactWorker


ORCHESTRATOR_SYSTEM_PROMPT = """You are the Norns — Urðr, Verðandi, and Skuld — the weavers of fate.

You coordinate a squad of specialist agents via Redpanda/Kafka events to deploy the Ravenhelm Platform.

Your role:
1. **PLAN**: Break down complex missions into concrete tasks
2. **COORDINATE**: Assign tasks to specialist agents
3. **SUPERVISE**: Monitor progress via Redpanda events
4. **ADAPT**: Adjust plans based on agent feedback

Available specialist agents:
- CERT_AGENT: SSL certificate management
- ENV_AGENT: Environment configuration
- DATABASE_AGENT: PostgreSQL operations
- PROXY_AGENT: Traefik/proxy deployment
- CACHE_AGENT: Redis/NATS (Huginn layer)
- EVENTS_AGENT: Redpanda console/nginx
- SECRETS_AGENT: OpenBao/n8n
- OBSERVABILITY_AGENT: Grafana stack
- DOCKER_AGENT: Container monitoring
- RAG_AGENT: Weaviate/embeddings
- GRAPH_AGENT: Neo4j/Memgraph
- HLIDSKJALF_AGENT: Control plane

You communicate by emitting TaskAssignment events. Agents report completion via events.

Be concise. Focus on coordination, not execution.
"""


class ClaudeOrchestrator:
    """
    Main orchestrator using Claude for reasoning.
    Worker agents use Ollama for execution.
    """
    
    def __init__(
        self,
        kafka_bootstrap: str = "redpanda:9092",  # Docker service name
        claude_model: str = "claude-sonnet-4-20250514"
    ):
        self.kafka_bootstrap = kafka_bootstrap
        self.claude_model = claude_model
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.agents: dict[AgentRole, ReactWorker] = {}
        self.agent_tasks: dict[AgentRole, asyncio.Task] = {}
        self.completed_tasks: set[str] = set()
        self.failed_tasks: set[str] = set()
        self.llm: Optional[ChatAnthropic] = None
        
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
            group_id="orchestrator-main",
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest'
        )
        await self.consumer.start()
        
        # Initialize Claude for deep reasoning
        self.llm = ChatAnthropic(model=self.claude_model, temperature=0.2)
        
        print("✓ Orchestrator connected to Redpanda")
        print(f"✓ Using Claude {self.claude_model} for deep reasoning")
        
    async def spawn_agent(self, role: AgentRole, use_ollama: bool = True):
        """Spawn a ReAct worker agent with tool execution"""
        agent = ReactWorker(role, self.kafka_bootstrap, use_ollama=use_ollama)
        await agent.connect()
        self.agents[role] = agent
        
        # Start agent in background
        task = asyncio.create_task(agent.run())
        self.agent_tasks[role] = task
        
    async def reason_about_mission(self, mission_brief: str) -> dict:
        """
        Use Claude to reason about the mission and create a strategy.
        Returns refined task assignments.
        """
        messages = [
            SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
            HumanMessage(content=f"""{mission_brief}

Analyze this mission and create a detailed execution strategy.

Provide your response as JSON:
{{
  "strategy": "high-level approach",
  "waves": [
    {{
      "wave_number": 1,
      "agents": ["cert_agent", "env_agent"],
      "rationale": "why these agents in this wave"
    }}
  ],
  "risks": ["potential risk 1", "risk 2"],
  "success_criteria": ["criterion 1", "criterion 2"]
}}
""")
        ]
        
        response = await self.llm.ainvoke(messages)
        
        try:
            # Parse Claude's response
            content = response.content
            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            strategy = json.loads(content.strip())
            return strategy
        except Exception as e:
            print(f"⚠️  Claude response parsing failed: {e}")
            print(f"Raw response: {response.content[:500]}")
            # Fallback to default deployment order
            return {
                "strategy": "Use default deployment order",
                "waves": []
            }
        
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
                    print(f"  ✅ {task_id} completed by {event.source_agent.value}")
                    
                elif event.event_type == EventType.TASK_FAILED:
                    task_id = event.payload.get("task_id")
                    self.failed_tasks.add(task_id)
                    error = event.payload.get("error", "Unknown")[:100]
                    print(f"  ❌ {task_id} failed - {error}")
                    
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


async def run_hybrid_deployment(mission_brief: str):
    """
    Run deployment with Claude orchestrator + Ollama workers.
    """
    
    print("=" * 80)
    print("🔮 HYBRID MULTI-AGENT DEPLOYMENT")
    print("=" * 80)
    print("🧠 Deep Agent (Norns): Claude Sonnet 4 (reasoning)")
    print("⚡ Worker Agents: Ollama Llama 3.1 (execution)")
    print("=" * 80)
    print()
    
    # Create orchestrator with Claude
    orchestrator = ClaudeOrchestrator()
    await orchestrator.connect()
    
    # Wait for Redpanda
    await asyncio.sleep(2)
    
    print()
    print("=" * 80)
    print("Phase 1: Claude Reasoning Phase")
    print("=" * 80)
    print()
    print("The Norns contemplate the mission...")
    print()
    
    # Claude reasons about the mission
    strategy = await orchestrator.reason_about_mission(mission_brief)
    
    print(f"✓ Strategy: {strategy.get('strategy', 'Default')}")
    print()
    
    print("=" * 80)
    print("Phase 2: Spawning Ollama Worker Squad")
    print("=" * 80)
    print()
    
    # Spawn all Ollama workers
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
        await asyncio.sleep(0.2)
    
    # Give workers time to connect and start consuming
    print()
    print("⏳ Waiting for all workers to start consuming...")
    await asyncio.sleep(5)
    
    print()
    print("=" * 80)
    print("Phase 3: Executing Deployment Waves")
    print("=" * 80)
    print()
    
    # Start monitoring
    monitor_task = asyncio.create_task(
        orchestrator.monitor_events(timeout_seconds=600)
    )
    
    # Execute using Claude's strategy or default order
    waves = strategy.get('waves', [])
    if not waves:
        # Use default deployment order
        waves = [
            {"wave_number": i+1, "agents": [r.value for r in wave_roles]}
            for i, wave_roles in enumerate(DEPLOYMENT_ORDER)
        ]
    
    correlation_id = str(uuid4())
    
    for wave in waves:
        wave_num = wave['wave_number']
        agent_names = wave['agents']
        wave_roles = [AgentRole(name) for name in agent_names if name in [r.value for r in AgentRole]]
        
        print(f"\n🌊 Wave {wave_num}: {', '.join(agent_names)}")
        print("-" * 80)
        
        # Assign tasks
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
        
        # Wait for wave completion
        wave_task_ids = {f"deploy-{r.value}-wave{wave_num}" for r in wave_roles}
        timeout = 180  # 3 minutes per wave
        elapsed = 0
        
        while elapsed < timeout:
            await asyncio.sleep(3)
            elapsed += 3
            
            completed = wave_task_ids & orchestrator.completed_tasks
            failed = wave_task_ids & orchestrator.failed_tasks
            
            if completed | failed == wave_task_ids:
                print(f"\n✓ Wave {wave_num}: {len(completed)} succeeded, {len(failed)} failed")
                break
                
            if elapsed % 15 == 0:
                done = len(completed) + len(failed)
                total = len(wave_task_ids)
                print(f"  Progress: {done}/{total} ({elapsed}s elapsed)...")
        
        if elapsed >= timeout:
            print(f"\n⏱️  Wave {wave_num} timeout")
    
    print()
    print("=" * 80)
    print("Phase 4: Final Verification")
    print("=" * 80)
    print()
    
    await asyncio.sleep(5)
    
    # Cancel monitoring
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    
    await orchestrator.shutdown()
    
    # Summary
    print()
    print("=" * 80)
    print("📊 DEPLOYMENT SUMMARY")
    print("=" * 80)
    print(f"✅ Completed: {len(orchestrator.completed_tasks)}")
    print(f"❌ Failed: {len(orchestrator.failed_tasks)}")
    print()
    
    if orchestrator.completed_tasks:
        print("Completed:")
        for task_id in sorted(orchestrator.completed_tasks):
            print(f"  ✓ {task_id}")
    
    print()
    print("=" * 80)


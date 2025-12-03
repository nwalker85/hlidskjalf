#!/usr/bin/env python3
"""
Multi-Agent Platform Orchestration Script

This script uses the Norns agent to spawn specialized agents that coordinate
via Redpanda events to deploy the entire Ravenhelm platform.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Setup paths - add hlidskjalf directory so 'src' can be imported
workspace_root = Path(__file__).parent.resolve()
hlidskjalf_root = workspace_root / "hlidskjalf"

# Add hlidskjalf directory to path so we can import src.norns...
sys.path.insert(0, str(hlidskjalf_root))

# Change working directory
os.chdir(str(hlidskjalf_root))

# Import from src package
from src.norns.agent import NornsAgent
from src.norns.squad_schema import (
    AGENT_PROMPTS,
    DEPLOYMENT_ORDER,
    AgentRole,
    Topics,
)


ORCHESTRATION_PLAN = """
# Ravenhelm Platform Multi-Agent Deployment

You are the orchestrating Norns. Your mission: Deploy the complete Ravenhelm platform
using a squad of specialized agents coordinated via Redpanda events.

## Phase 1: Initialize Event Infrastructure

First, we need Redpanda running for agent coordination:

1. Check if Redpanda is already running: `docker compose ps redpanda`
2. If not healthy, restart it: `docker compose up -d redpanda`
3. Wait for health check (30-60 seconds)
4. Create the squad coordination topics:

```bash
# Create all coordination topics
for topic in squad.coordination squad.certs squad.docker squad.config squad.proxy squad.database squad.cache squad.events squad.secrets squad.observability squad.rag squad.graph squad.hlidskjalf squad.health squad.tasks; do
  docker compose exec -T redpanda rpk topic create ravenhelm.$topic --brokers localhost:9092 || true
done
```

## Phase 2: Deploy in Waves

Once Redpanda is ready and topics are created, spawn specialist agents in dependency order:

### Wave 1: Prerequisites (run in parallel)
- **CERT_AGENT**: Copy certificates from ravenhelm-proxy/config/certs/ to config/certs/
- **ENV_AGENT**: Validate .env file has required keys
- **DATABASE_AGENT**: Verify PostgreSQL is healthy (already running)

### Wave 2: Core Infrastructure (after Wave 1)
- **PROXY_AGENT**: Start ravenhelm-proxy (cd ravenhelm-proxy && docker compose up -d)
- **CACHE_AGENT**: Start Redis and NATS (docker compose up -d redis nats)
- **SECRETS_AGENT**: Verify OpenBao and start vault-nginx

### Wave 3: Event Layer & Monitoring (after Wave 2)
- **EVENTS_AGENT**: Start redpanda-console and events-nginx
- **OBSERVABILITY_AGENT**: Fix LangFuse/observe-nginx, verify Grafana stack
- **DOCKER_AGENT**: Monitor all containers (docker compose ps)

### Wave 4: Data Layers (after Wave 3)
- **RAG_AGENT**: Start embeddings, Weaviate, reranker, docling
- **GRAPH_AGENT**: Start Memgraph and Neo4j

### Wave 5: Control Plane (after Wave 4)
- **HLIDSKJALF_AGENT**: Build and start Hlidskjalf API and UI

## Agent Coordination

Each agent should:
1. Check its dependencies are satisfied
2. Execute its tasks
3. Report progress via terminal output (we'll simulate Redpanda events)
4. Emit completion status

## Execution Strategy

Since we're in a single process, spawn each agent as a subagent with:
- Their specific prompt from AGENT_PROMPTS
- The tasks they need to complete
- Instructions to report status

For each wave:
1. Spawn all agents in that wave in parallel
2. Collect their results
3. Verify all succeeded before proceeding to next wave

## Tools Available

You have access to:
- `execute_terminal_command`: Run docker, bash commands
- `workspace_read/write`: Read/write files
- `spawn_subagent`: Create specialist agents
- `write_todos`: Track progress

## Success Criteria

All agents report completion and:
- All 32 services from docker-compose.yml are running
- No containers in restart loop
- ravenhelm-proxy routing traffic
- Hlidskjalf accessible at https://hlidskjalf.ravenhelm.test

BEGIN ORCHESTRATION NOW.
"""


async def main():
    print("=" * 80)
    print("RAVENHELM PLATFORM DEPLOYMENT - MULTI-AGENT ORCHESTRATION")
    print("=" * 80)
    print()
    print("Initializing the Norns orchestrator...")
    print()
    
    # Create Norns agent
    agent = NornsAgent(session="platform-deployment")
    thread_id = "platform-deployment-001"
    
    print("📜 Presenting the deployment plan to the Norns...")
    print()
    
    # Give the Norns the orchestration plan
    response_buffer = []
    async for chunk in agent.stream(ORCHESTRATION_PLAN, thread_id=thread_id):
        sys.stdout.write(chunk)
        sys.stdout.flush()
        response_buffer.append(chunk)
    
    print()
    print()
    print("=" * 80)
    print("ORCHESTRATION COMPLETE")
    print("=" * 80)
    
    # Check final status
    print()
    print("Checking platform status...")
    
    status_check = """
    Check the final status of the deployment:
    1. Run: docker compose ps --format "table {{.Name}}\t{{.Status}}" | head -40
    2. Count how many services are running vs total expected (32)
    3. Check for any containers in restart loop
    4. Test key endpoints if ravenhelm-proxy is running
    
    Provide a summary of what succeeded, what failed, and next steps.
    """
    
    print()
    async for chunk in agent.stream(status_check, thread_id=thread_id):
        sys.stdout.write(chunk)
        sys.stdout.flush()
    
    print()
    print()
    print("=" * 80)
    print("Deployment orchestration completed!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nOrchestration interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nOrchestration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


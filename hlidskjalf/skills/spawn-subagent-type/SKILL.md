---
name: spawn-subagent-type
description: Create a new specialized subagent type with defined skills and tools, build it as a Docker image, deploy it, and register it in the platform registries.
version: 1.0.0
author: Norns
tags:
  - meta
  - agents
  - deployment
  - docker
  - registry
  - infrastructure
triggers:
  - create new agent type
  - spawn subagent type
  - build agent image
  - deploy new agent
  - create specialized agent
dependencies:
  - docker-operations
  - create-skill
---

# Spawn Subagent Type

This skill enables the Norns to create entirely new specialized subagent types, package them as Docker containers, deploy them to the platform, and register them for orchestration.

## Overview

Creating a new subagent type involves:
1. **Define the agent** - Name, purpose, skills, and tools
2. **Generate the code** - Python module with LangGraph implementation
3. **Create Dockerfile** - Containerize the agent
4. **Build the image** - Docker build with proper tags
5. **Deploy the container** - Start with allocated port
6. **Update registries** - Track in port_registry.yaml and agent_registry.yaml

## Step 1: Define the Subagent

Before creating, define these parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `agent_name` | kebab-case identifier | `security-scanner` |
| `agent_class` | PascalCase class name | `SecurityScannerAgent` |
| `description` | What the agent does | "Scans for security vulnerabilities" |
| `model` | LLM to use | `ollama/llama3.1` or `gpt-4o` |
| `skills` | List of skill names | `["analyze-logs", "docker-operations"]` |
| `tools` | Custom tools to include | `["scan_ports", "check_cves"]` |
| `base_port` | Starting port range | `8100` |

## Step 2: Generate Agent Code

Create the agent module at `hlidskjalf/src/agents/{agent_name}/`:

```python
# hlidskjalf/src/agents/{agent_name}/__init__.py
"""
{Agent Name} - {Description}
Auto-generated subagent type.
"""

from .agent import {AgentClass}, create_{agent_name}_graph
from .tools import {AGENT_NAME}_TOOLS

__all__ = ["{AgentClass}", "create_{agent_name}_graph", "{AGENT_NAME}_TOOLS"]
```

```python
# hlidskjalf/src/agents/{agent_name}/agent.py
from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END, add_messages
from langgraph.prebuilt import ToolNode

from .tools import {AGENT_NAME}_TOOLS

class {AgentClass}State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    context: dict

SYSTEM_PROMPT = """{description}

You are a specialized subagent in the Ravenhelm platform.
Use your tools to accomplish tasks delegated by the Norns orchestrator.

Available Skills: {skills}
"""

def create_{agent_name}_graph():
    from langchain_openai import ChatOpenAI  # or ChatOllama
    
    llm = ChatOpenAI(model="{model}").bind_tools({AGENT_NAME}_TOOLS)
    
    def agent_node(state):
        response = llm.invoke(state["messages"])
        return {{"messages": [response]}}
    
    def should_continue(state):
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END
    
    workflow = StateGraph({AgentClass}State)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode({AGENT_NAME}_TOOLS))
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {{"tools": "tools", END: END}})
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()

{AGENT_NAME}_GRAPH = create_{agent_name}_graph()
```

```python
# hlidskjalf/src/agents/{agent_name}/tools.py
from langchain_core.tools import tool

# Define agent-specific tools here
@tool
def example_tool(input: str) -> str:
    """Example tool for {agent_name}."""
    return f"Processed: {{input}}"

{AGENT_NAME}_TOOLS = [
    example_tool,
    # Add more tools...
]
```

## Step 3: Create Dockerfile

```dockerfile
# hlidskjalf/src/agents/{agent_name}/Dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    langchain \
    langchain-openai \
    langgraph \
    "langgraph-cli[inmem]"

# Copy agent code
COPY . /app/agent/

# Create langgraph config
RUN echo '{{ \
  "python_version": "3.13", \
  "dependencies": ["."], \
  "graphs": {{ \
    "{agent_name}": "./agent/agent.py:{AGENT_NAME}_GRAPH" \
  }} \
}}' > /app/langgraph.json

ENV PYTHONPATH=/app

EXPOSE {port}

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s \
    CMD curl -f http://localhost:{port}/info || exit 1

CMD ["langgraph", "dev", "--host", "0.0.0.0", "--port", "{port}", "--no-browser"]
```

## Step 4: Build Docker Image

```bash
# Navigate to agent directory
cd hlidskjalf/src/agents/{agent_name}

# Build with ravenhelm namespace
docker build -t ravenhelm/{agent_name}:latest .

# Tag with version
docker tag ravenhelm/{agent_name}:latest ravenhelm/{agent_name}:1.0.0
```

## Step 5: Deploy Container

```bash
# Allocate port (check port_registry.yaml first!)
PORT={allocated_port}

# Run container
docker run -d \
  --name ravenhelm-{agent_name} \
  --network platform_net \
  -p $PORT:$PORT \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  --restart unless-stopped \
  --label "ravenhelm.project=hlidskjalf" \
  --label "ravenhelm.service={agent_name}" \
  --label "ravenhelm.workload=subagent" \
  ravenhelm/{agent_name}:latest
```

## Step 6: Update Registries

### Port Registry (config/port_registry.yaml)

```yaml
# Add entry under agents section
agents:
  {agent_name}:
    port: {allocated_port}
    protocol: http
    health_endpoint: /info
    description: "{description}"
```

### Agent Registry (config/agent_registry.yaml)

```yaml
# Add new agent type
agents:
  {agent_name}:
    name: "{Agent Name}"
    class: "{AgentClass}"
    description: "{description}"
    version: "1.0.0"
    model: "{model}"
    port: {allocated_port}
    status: active
    skills:
      - skill1
      - skill2
    tools:
      - tool1
      - tool2
    container:
      image: "ravenhelm/{agent_name}:latest"
      network: "platform_net"
      restart_policy: "unless-stopped"
    created_at: "{timestamp}"
    created_by: "norns"
```

### Docker Compose (docker-compose.yml)

Add service definition:

```yaml
  {agent_name}:
    image: ravenhelm/{agent_name}:latest
    container_name: ravenhelm-{agent_name}
    labels:
      - "ravenhelm.project=hlidskjalf"
      - "ravenhelm.service={agent_name}"
      - "ravenhelm.workload=subagent"
    ports:
      - "{port}:{port}"
    environment:
      - OPENAI_API_KEY=${{OPENAI_API_KEY}}
    networks:
      - platform_net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{port}/info"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
```

## Complete Automation Script

For fully automated deployment, run:

```bash
#!/bin/bash
# scripts/spawn-subagent.sh

AGENT_NAME=$1
DESCRIPTION=$2
MODEL=${3:-"gpt-4o-mini"}
BASE_PORT=${4:-8100}

# Find next available port
NEXT_PORT=$(python3 -c "
import yaml
with open('config/port_registry.yaml') as f:
    reg = yaml.safe_load(f)
ports = [a.get('port', 0) for a in reg.get('agents', {}).values()]
print(max(ports + [$BASE_PORT]) + 1)
")

echo "Creating agent: $AGENT_NAME on port $NEXT_PORT"

# Create directory structure
mkdir -p hlidskjalf/src/agents/$AGENT_NAME

# Generate files (use templates)
# ... generate __init__.py, agent.py, tools.py, Dockerfile ...

# Build image
docker build -t ravenhelm/$AGENT_NAME:latest hlidskjalf/src/agents/$AGENT_NAME

# Deploy
docker run -d \
  --name ravenhelm-$AGENT_NAME \
  --network platform_net \
  -p $NEXT_PORT:$NEXT_PORT \
  ravenhelm/$AGENT_NAME:latest

# Update registries
# ... update port_registry.yaml, agent_registry.yaml, docker-compose.yml ...

echo "✓ Agent $AGENT_NAME deployed on port $NEXT_PORT"
```

## Verification Checklist

After spawning a new agent type:

- [ ] Agent code compiles without errors
- [ ] Docker image builds successfully
- [ ] Container starts and passes health check
- [ ] Port is correctly registered
- [ ] Agent responds to `/info` endpoint
- [ ] Agent can execute its tools
- [ ] Norns can communicate with the agent
- [ ] docker-compose.yml is updated

## Example: Creating a Security Scanner Agent

```bash
# 1. Define the agent
AGENT_NAME="security-scanner"
DESCRIPTION="Scans infrastructure for security vulnerabilities"
MODEL="gpt-4o-mini"

# 2. Create using the spawn tool
norns spawn-agent-type \
  --name $AGENT_NAME \
  --description "$DESCRIPTION" \
  --model $MODEL \
  --skills "analyze-logs,docker-operations" \
  --tools "scan_ports,check_cves,audit_configs"

# 3. Verify deployment
curl http://localhost:8101/info
```

## Rollback Procedure

If deployment fails:

```bash
# Stop and remove container
docker stop ravenhelm-{agent_name}
docker rm ravenhelm-{agent_name}

# Remove image
docker rmi ravenhelm/{agent_name}:latest

# Revert registry changes
git checkout config/port_registry.yaml
git checkout config/agent_registry.yaml
git checkout docker-compose.yml

# Clean up agent code
rm -rf hlidskjalf/src/agents/{agent_name}
```


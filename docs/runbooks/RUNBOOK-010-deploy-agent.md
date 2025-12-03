# RUNBOOK-010: Deploy New Agent Type

> **Category:** Agent Operations  
> **Priority:** Normal Change  
> **Approval Required:** Technical Lead  
> **Last Updated:** 2024-12-03

---

## Prerequisites Checklist

Before deploying a new agent:

- [ ] **Port Registry**: Reserve port in `config/port_registry.yaml`
- [ ] **Agent Registry**: Define agent in `config/agent_registry.yaml`
- [ ] **Networking**: Traefik route configured (if external access needed)
- [ ] **Certificates**: mkcert includes agent domain
- [ ] **Kafka Topics**: Required topics created
- [ ] **Skills**: Agent skills defined in `hlidskjalf/skills/`

---

## Step 1: Define Agent in Registry

Add to `config/agent_registry.yaml`:

```yaml
agents:
  my-new-agent:
    id: my-new-agent
    type: worker  # or: orchestrator, specialized
    role: "Description of what this agent does"
    model:
      provider: ollama  # or: anthropic, openai
      model_name: llama3.1:8b
    tools:
      - execute_terminal_command
      - read_file
      - write_file
      # Add relevant tools
    kafka_topics:
      subscribe:
        - ravenhelm.squad.tasks.my-new-agent
      publish:
        - ravenhelm.squad.coordination
    port: 8110  # From port registry
    health_endpoint: /info
    metrics_endpoint: /metrics
```

---

## Step 2: Create Agent Code

Create `hlidskjalf/src/agents/my-new-agent/`:

```bash
mkdir -p hlidskjalf/src/agents/my-new-agent
touch hlidskjalf/src/agents/my-new-agent/__init__.py
```

**`agent.py`:**
```python
"""My New Agent - Description"""

from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama

from src.norns.tools import NORN_TOOLS

SYSTEM_PROMPT = """You are a specialized agent for [purpose].

Your responsibilities:
1. [Responsibility 1]
2. [Responsibility 2]

Use your tools to accomplish tasks."""

def create_my_agent():
    llm = ChatOllama(
        model="llama3.1:8b",
        base_url="http://ollama:11434",
        temperature=0.1
    )
    
    agent = create_react_agent(
        llm,
        tools=NORN_TOOLS,
    )
    
    return agent

MY_AGENT = create_my_agent()
```

**`tools.py`:**
```python
"""Agent-specific tools"""

from langchain_core.tools import tool

@tool
def my_custom_tool(param: str) -> dict:
    """Description of what this tool does.
    
    Args:
        param: Description of parameter
        
    Returns:
        Result description
    """
    # Implementation
    return {"status": "success", "result": param}

MY_AGENT_TOOLS = [my_custom_tool]
```

---

## Step 3: Create Dockerfile

`hlidskjalf/src/agents/my-new-agent/Dockerfile`:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY hlidskjalf/pyproject.toml ./hlidskjalf/
COPY hlidskjalf/src ./hlidskjalf/src/
COPY hlidskjalf/README.md ./hlidskjalf/

RUN pip install --no-cache-dir -e ./hlidskjalf

EXPOSE 8110

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8110/info || exit 1

CMD ["python", "-m", "uvicorn", "hlidskjalf.src.agents.my-new-agent.api:app", "--host", "0.0.0.0", "--port", "8110"]
```

---

## Step 4: Add to Docker Compose

Add to `docker-compose.yml`:

```yaml
services:
  my-new-agent:
    build:
      context: .
      dockerfile: hlidskjalf/src/agents/my-new-agent/Dockerfile
    container_name: gitlab-sre-my-new-agent
    ports:
      - "8110:8110"
    environment:
      - OLLAMA_URL=http://ollama:11434
      - KAFKA_BOOTSTRAP=redpanda:9092
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./hlidskjalf/src:/app/hlidskjalf/src:ro
    depends_on:
      ollama:
        condition: service_healthy
      redpanda:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8110/info"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - gitlab-network
    labels:
      - "ravenhelm.agent=my-new-agent"  # For SPIRE registration
```

---

## Step 5: Create Kafka Topics

```bash
# Create required topics
docker compose exec -T redpanda rpk topic create \
  ravenhelm.squad.tasks.my-new-agent \
  --partitions 3 \
  --replicas 1

# Verify
docker compose exec -T redpanda rpk topic list | grep my-new-agent
```

---

## Step 6: Build and Deploy

```bash
# Build agent image
docker compose build my-new-agent

# Deploy
docker compose up -d my-new-agent

# Check logs
docker compose logs my-new-agent --tail 20

# Verify health
curl http://localhost:8110/info
```

---

## Step 7: Register with SPIRE (if mTLS enabled)

```bash
# Add SPIRE entry
docker compose exec -T spire-server /opt/spire/bin/spire-server entry create \
  -spiffeID spiffe://ravenhelm.local/agent/my-new-agent \
  -parentID spiffe://ravenhelm.local/spire/agent/docker \
  -selector docker:label:ravenhelm.agent:my-new-agent \
  -ttl 1800
```

---

## Step 8: Test Agent

```bash
# Send test task via Kafka
echo '{"task_id":"test-001","type":"test","payload":{"message":"hello"}}' | \
  docker compose exec -T redpanda rpk topic produce ravenhelm.squad.tasks.my-new-agent

# Watch agent response
docker compose exec -T redpanda rpk topic consume ravenhelm.squad.coordination --follow
```

---

## Step 9: Update Documentation

- [ ] Add to README.md agent table
- [ ] Create agent-specific runbook if complex
- [ ] Document any new tools in reference docs

---

## Rollback Procedure

```bash
# Stop and remove agent
docker compose stop my-new-agent
docker compose rm -f my-new-agent

# Clean up Kafka topics
docker compose exec -T redpanda rpk topic delete ravenhelm.squad.tasks.my-new-agent

# Revert registry changes
git checkout config/agent_registry.yaml config/port_registry.yaml
```

---

## Cost Considerations

| Model | Cost | Use Case |
|-------|------|----------|
| Ollama (local) | $0/task | Development, high-volume |
| GPT-4o-mini | $0.15/MTok | Simple classification |
| GPT-4o | $2.50/MTok | Complex reasoning |
| Claude Sonnet | $3.00/MTok | Deep reasoning |

---

## References

- [RUNBOOK-001: Deploy Docker Service](./RUNBOOK-001-deploy-docker-service.md)
- [Agent Registry](../../config/agent_registry.yaml)
- [Skills Documentation](../../hlidskjalf/skills/)


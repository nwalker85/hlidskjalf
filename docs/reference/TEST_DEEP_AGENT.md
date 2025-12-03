# Testing the Norns Deep Agent with 15 Subagents

## Quick Test

```bash
cd /Users/nwalker/Development/hlidskjalf
source .venv313/bin/activate

# Test the deep agent directly
python3 << 'EOF'
import asyncio
from hlidskjalf.src.norns.deep_agent import ask_the_norns

async def test():
    response = await ask_the_norns("""
    I need you to coordinate the completion of the Ravenhelm Platform deployment.
    
    Current status: 17/32 services running
    
    Priority tasks:
    1. Fix SSL certificates (use security_specialist)
    2. Check network configuration (use network_specialist)  
    3. Estimate remaining cost (use cost_analyst)
    4. Assess security risks (use risk_assessor)
    5. Create deployment plan (use project_coordinator)
    
    Delegate to your specialists and report back.
    """)
    
    print(response)

asyncio.run(test())
EOF
```

## Frontend Test

### 1. Update Routes

Add to `hlidskjalf/src/main.py`:

```python
from src.api.norns_deep_api import router as norns_router

app.include_router(norns_router)
```

### 2. Start Backend

```bash
cd hlidskjalf
uvicorn src.main:app --reload --host 0.0.0.0 --port 8900
```

### 3. Start Frontend

```bash
cd hlidskjalf/ui
npm run dev
```

### 4. Access UI

Open: `http://localhost:3900/norns`

## API Endpoints

### Chat with Norns

```bash
curl -X POST http://localhost:8900/api/v1/norns/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Deploy SPIRE and configure mTLS",
    "thread_id": "test-001"
  }'
```

### List Subagents

```bash
curl http://localhost:8900/api/v1/norns/subagents
```

### Stream Observability

```bash
curl -N http://localhost:8900/api/v1/norns/observability/stream
```

## Expected Behavior

### Example Interaction

**User:** "I need to deploy Zitadel with OAuth 2.1 security"

**Norns Response:**
```
Verðandi observes the current state...

I shall coordinate multiple specialists for this task:

1. First, I'll consult the schema_architect to review the Zitadel database schema.
   [Invoking: schema_architect]
   
2. Then, the app_installer will deploy the Zitadel service.
   [Invoking: app_installer]
   
3. The sso_identity_expert will configure OAuth 2.1 clients.
   [Invoking: sso_identity_expert]
   
4. The security_specialist will verify SSL/TLS configuration.
   [Invoking: security_specialist]
   
5. Finally, the qa_engineer will test the authentication flow.
   [Invoking: qa_engineer]

[Results from specialists compiled...]

✓ Zitadel deployed at https://zitadel.ravenhelm.test
✓ OAuth 2.1 clients created for 12 agents
✓ TLS 1.3 verified
✓ Authentication flow tested successfully

The identity provider is now operational.
```

## Observability Stream

The observability_monitor agent streams ALL agent activity:

```
[2024-12-02 08:30:15] orchestrator assigned task to security_specialist
[2024-12-02 08:30:16] security_specialist started: verify-certificates
[2024-12-02 08:30:18] security_specialist completed: Certificates valid
[2024-12-02 08:30:19] orchestrator assigned task to app_installer
[2024-12-02 08:30:20] app_installer started: deploy-zitadel
[2024-12-02 08:30:45] app_installer completed: Zitadel running
```

## Specialist Agent Examples

### File Manager

```python
response = await ask_the_norns("""
Find all Python files that import 'langchain' and list them.
Then read the imports from the first 3 files.

Use the file_manager specialist.
""")
```

### Security Specialist

```python
response = await ask_the_norns("""
Generate a new SSL certificate for *.ravenhelm.test using mkcert.
Copy it to all services that need it.
Verify the certificate is valid and has the right SANs.

Use the security_specialist.
""")
```

### Cost Analyst

```python
response = await ask_the_norns("""
Calculate the estimated monthly cost for running the Ravenhelm Platform with:
- 1 Claude orchestrator (1M tokens/month)
- 12 Ollama workers (local)
- AWS infrastructure (current docker-compose equivalent)

Break down costs by category.

Use the cost_analyst.
""")
```

### Project Coordinator

```python
response = await ask_the_norns("""
Create a GitHub project board for completing the Ravenhelm deployment.
Break it into milestones: Security, Cost Tracking, Operations.
Create issues for each task.

Use the project_coordinator.
""")
```

### Observability Monitor

```python
response = await ask_the_norns("""
Show me what all agents have been doing for the last 10 minutes.
Which agents completed tasks? Which failed? Any anomalies?

Use the observability_monitor to analyze the event stream.
""")
```

## Composio Integration

Subagents that use Composio tools (installed: `composio-langchain`):

- **project_coordinator**: GitHub Issues, PR management
- **file_manager**: Advanced git operations
- **app_installer**: Shell execution with safety
- **devops_engineer**: GitHub workflows

### Composio Authentication

```bash
# Setup Composio (one-time)
composio login

# Connect integrations
composio add github
composio add notion
composio add slack

# List available actions
composio actions github --limit 20
```

## Frontend Features

### Main Chat Interface

- Chat with the Norns at `/norns`
- Real-time streaming responses
- Shows which Norn is speaking (Urðr, Verðandi, Skuld)
- Thread-based conversations

### Subagent Status Panel

- Live view of all 15 specialists
- Shows which agents are currently working
- Status indicators (ready, working, idle)
- Task completion counts

### Observability Dashboard

- Real-time log stream from agent swarm
- Event type filtering
- Agent activity timeline
- Performance metrics

## Production Deployment

### Environment Variables

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...  # For Claude orchestrator
OPENAI_API_KEY=sk-...         # Optional fallback
COMPOSIO_API_KEY=...          # For enterprise tools

# Observability
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...

# Event bus
NATS_URL=nats://localhost:4222
KAFKA_BOOTSTRAP_SERVERS=localhost:19092
```

### Docker Deployment

```yaml
# docker-compose.yml (add to services)

hlidskjalf:
  # ... existing config
  environment:
    - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    - COMPOSIO_API_KEY=${COMPOSIO_API_KEY}
    - NATS_URL=nats://nats:4222
    - KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: norns-deep-agent
spec:
  replicas: 1  # Single orchestrator
  template:
    spec:
      containers:
      - name: hlidskjalf
        image: ravenhelm/hlidskjalf:latest
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: ai-keys
              key: anthropic
        - name: COMPOSIO_API_KEY
          valueFrom:
            secretKeyRef:
              name: integrations
              key: composio
```

## Monitoring the Deep Agent

### Metrics to Track

```yaml
deep_agent_metrics:
  orchestrator:
    - llm_calls_per_minute
    - reasoning_latency_p95
    - subagent_delegations_count
    - cost_per_interaction_usd
  
  subagents:
    - active_subagents_count
    - tasks_completed_per_subagent
    - subagent_success_rate
    - subagent_latency_p95
  
  system:
    - total_agents_spawned: 16 (1 orchestrator + 15 specialists)
    - event_bus_lag_ms
    - end_to_end_latency_p99
```

### Grafana Dashboard Queries

```promql
# Subagent invocation rate
rate(norns_subagent_invocations_total[5m])

# Cost per subagent
sum by (subagent) (norns_subagent_cost_usd)

# Success rate
(
  rate(norns_subagent_success_total[5m])
  / 
  rate(norns_subagent_invocations_total[5m])
) * 100
```

## Troubleshooting

### Subagent Not Responding

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Check if model is available
ollama list | grep llama3.1

# Test subagent directly
python -c "
from src.norns.specialized_agents import create_file_management_agent
agent = create_file_management_agent()
print(agent.name, agent.description)
"
```

### Observability Stream Not Working

```bash
# Check Kafka is accessible
docker compose ps redpanda

# Test Kafka consumer
docker compose exec -T redpanda rpk topic list

# Check consumer groups
docker compose exec -T redpanda rpk group list | grep observability
```

### Composio Tools Failing

```bash
# Re-authenticate
composio login

# Check connected integrations
composio apps

# Test GitHub connection
composio apps update github
```

## Next Steps

1. **Test basic chat:** Ask the Norns simple questions
2. **Test delegation:** Ask for tasks requiring specialists
3. **Test observability:** Use observability_monitor to watch the swarm
4. **Add more subagents:** Create specialists for your specific needs
5. **Integrate Composio:** Connect GitHub, Slack, Notion for enterprise tools

---

**The Norns are ready to coordinate 15 specialists. Let them weave your fate.** 🔮


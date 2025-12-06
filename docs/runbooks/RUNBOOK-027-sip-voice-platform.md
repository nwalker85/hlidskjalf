# RUNBOOK-027: SIP Voice AI Platform Integration

> **Purpose**: Deploy enterprise telephony AI platform with inbound/outbound SIP calling, intelligent call routing, and multi-agent escalation  
> **Scope**: LiveKit agents, SIP integration, Twilio trunking, on-premises deployment readiness  
> **Audience**: Developers implementing voice AI for regulated industries (healthcare, finance, government)

---

## Prerequisites

- [ ] LiveKit server accessible (cloud or self-hosted)
- [ ] Twilio SIP trunk configured (`ST_g7VzsNvaXJFi` or equivalent)
- [ ] API keys: Deepgram (STT), ElevenLabs (TTS), OpenAI (LLM)
- [ ] Port registry entry reserved (see below)
- [ ] Docker Compose 2.x

---

## 1. Port Registry Entry

Register in `/Users/nwalker/Development/hlidskjalf/config/port_registry.yaml`:

```yaml
work:
  sip:
    path: ~/Development/Quant/SIP
    api_port: 8207
    ui_port: 3207
    domain: sip.ravenhelm.test
    domain_aliases:
      - sip-api.ravenhelm.test
      - sip-langgraph.ravenhelm.test
    realm: alfheim
    status: development
    git_remote: github.com-quant
    description: SIP voice orchestration platform with LiveKit agents
    services:
      - name: backend
        port: 8207
        internal_port: 8000
        protocol: http
        health_endpoint: /health
        note: FastAPI orchestration API + LiveKit control plane
      - name: frontend
        port: 3207
        internal_port: 3000
        protocol: http
        note: Next.js operator console
      - name: langgraph
        port: 8208
        internal_port: 8001
        protocol: http
        note: LangGraph agents runtime
```

Update `next_available`:
```yaml
next_available:
  work_api: 8209
  work_ui: 3208
```

---

## 2. Traefik Routing

Add to `/Users/nwalker/Development/hlidskjalf/ravenhelm-proxy/dynamic.yml`:

```yaml
http:
  routers:
    sip-ui:
      rule: "Host(`sip.ravenhelm.test`)"
      service: sip-ui-svc
      middlewares:
        - secure-headers
      tls: {}
    
    sip-api:
      rule: "Host(`sip-api.ravenhelm.test`)"
      service: sip-api-svc
      middlewares:
        - cors-all
        - secure-headers
      tls: {}
    
    sip-langgraph:
      rule: "Host(`sip-langgraph.ravenhelm.test`)"
      service: sip-langgraph-svc
      middlewares:
        - cors-all
        - secure-headers
      tls: {}

  services:
    sip-ui-svc:
      loadBalancer:
        servers:
          - url: "http://host.docker.internal:3207"
    
    sip-api-svc:
      loadBalancer:
        servers:
          - url: "http://host.docker.internal:8207"
    
    sip-langgraph-svc:
      loadBalancer:
        servers:
          - url: "http://host.docker.internal:8208"
```

---

## 3. Environment Configuration

### Create `.env` in project root

```bash
cd ~/Development/Quant/SIP

# Copy template
cp env.template .env

# Or create BACKEND/.env.local directly (recommended)
cat > BACKEND/.env.local <<EOF
# LiveKit deployment
LIVEKIT_URL=wss://ravenhelm-gt6v1eh8.livekit.cloud
LIVEKIT_API_KEY=APIetNUyw5ZNWfN
LIVEKIT_API_SECRET=tlt13NsbFmfKZxZDnvM4qaifv1gyoD9eifCD3dmqmFsA
LIVEKIT_PROJECT_ID=p_2g0282esbg2
LIVEKIT_SIP_DOMAIN=ravenhelm-gt6v1eh8.pstn.livekit.cloud

# SIP trunk / telephony
SIP_OUTBOUND_TRUNK_ID=ST_g7VzsNvaXJFi
OUTBOUND_PHONE_NUMBER=+17372143330
SIP_URI=ravenhelm.pstn.twilio.com

# Speech + intelligence providers
DEEPGRAM_API_KEY=YOUR_DEEPGRAM_KEY
ELEVENLABS_API_KEY=YOUR_ELEVENLABS_KEY
OPENAI_API_KEY=YOUR_OPENAI_KEY

# Port assignments (aligned with registry)
BACKEND_PORT=8207
FRONTEND_PORT=3207
LANGGRAPH_PORT=8208
EOF
```

---

## 4. Deployment

### Option A: Cloud LiveKit (Development - Fastest)

**Best for**: Quick iteration, no networking complexity

```bash
cd ~/Development/Quant/SIP

# Start core services
docker compose up -d backend agent-worker langgraph

# Verify health
curl http://localhost:8207/health
# Expected: {"status":"healthy"}

# Check agent worker connected
docker compose logs agent-worker | grep "registered worker"
# Should show: "registered worker" with LiveKit URL
```

**Services Running**:
- Backend API: http://localhost:8207
- Frontend UI: http://localhost:3207
- LangGraph: http://localhost:8208
- Agent Worker: Connected to cloud LiveKit

### Option B: Self-Hosted LiveKit (Enterprise/On-Prem)

**Best for**: Customer demos, regulated environments, air-gapped deployments

```bash
cd ~/Development/Quant/SIP

# Setup networking (one-time)
./scripts/setup-local-sip.sh

# Start full stack with self-hosted LiveKit
make up-local-sip

# Verify services
docker compose -f docker-compose.yml -f docker-compose.local-sip.yml ps

# Should show:
#   sip-livekit-local  ✅ (port 7880)
#   sip-livekit-sip    ✅ (port 5060/udp)
#   sip-redis          ✅ (port 6379)
#   + all other services
```

**Requires**:
- Port forwarding: UDP 5060, 10000-10100 (SIP + RTP)
- Public IP or VPS with stable IP
- See `docs/LOCAL_SIP_DEVELOPMENT.md` for detailed setup

---

## 5. Configure Twilio for Inbound Calls

### A. Setup ngrok Tunnel (HTTP webhook only)

```bash
# Install ngrok
brew install ngrok
ngrok config add-authtoken YOUR_TOKEN

# Start tunnel (keep running)
ngrok http 8207

# Note the HTTPS URL, example:
# Forwarding: https://abc123xyz.ngrok.io → http://localhost:8207
```

### B. Configure Twilio Phone Number

1. Go to Twilio Console: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming
2. Click on your number: `+17372143330`
3. Under **Voice Configuration**:
   - **Configure with**: Webhooks, TwiML Bins, Functions, Studio, or Proxy
   - **A call comes in**: `Webhook`
   - **URL**: `https://YOUR_NGROK_URL.ngrok.io/api/v1/sip/inbound/webhook`
   - **HTTP Method**: `POST`
   - **Status Callback** (optional): `https://YOUR_NGROK_URL.ngrok.io/api/v1/sip/inbound/status`
4. Click **Save**

### C. Test Inbound Call

```bash
# Terminal 1: Monitor logs
docker compose logs -f backend agent-worker

# Phone: Call your Twilio number
# Dial: +1-737-214-3330

# Expected flow:
# 1. Twilio receives call
# 2. Twilio HTTP POST → ngrok → backend webhook
# 3. Backend creates room + dispatches agent
# 4. Backend returns TwiML with LiveKit SIP URI
# 5. Twilio dials LiveKit via SIP
# 6. Agent worker joins room
# 7. Agent answers and greets caller
```

---

## 6. Outbound Call Testing

### Via Agent GUI

```bash
# Open in browser
open http://localhost:8207/agent/gui

# Fill in form:
# - Customer Name: Test Customer
# - Appointment Time: Today at 3pm
# - Phone Number: +14155550100 (your test number)
# - Transfer To: (optional)

# Click "Start Outbound Call"

# Monitor logs:
docker compose logs -f agent-worker
```

### Via API

```bash
curl -X POST http://localhost:8207/api/v1/agent/dial \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Jane Doe",
    "appointment_time": "Tuesday at 3pm",
    "phone_number": "+14155550100",
    "transfer_to": null
  }'

# Response:
# {
#   "status": "queued",
#   "room_name": "outbound-abc12345",
#   "customer_name": "Jane Doe",
#   ...
# }
```

---

## 7. Architecture Components

### Service Map

| Component | Purpose | Port | Health Check |
|-----------|---------|------|--------------|
| Backend (FastAPI) | API orchestration, webhook handler | 8207 | `/health` |
| Frontend (Next.js) | Operator console | 3207 | - |
| LangGraph | AI agent runtime | 8208 | `/info` |
| Agent Worker | LiveKit agent (STT/TTS/LLM) | - | Logs: "registered worker" |
| LiveKit (local) | WebRTC + SIP termination | 7880, 5060 | `/healthz` |
| Redis (local) | LiveKit state store | 6379 | `PING` |

### Call Flow (Inbound)

```
Caller dials +17372143330
  ↓
Twilio receives call
  ↓ (HTTP POST webhook)
Backend /api/v1/sip/inbound/webhook
  - Creates LiveKit room: "inbound-abc123"
  - Dispatches agent to room
  - Returns TwiML: <Dial><Sip>sip:inbound-abc123@livekit-domain</Sip></Dial>
  ↓ (Twilio executes TwiML)
Twilio dials LiveKit via SIP
  ↓
LiveKit SIP server accepts call
  - Creates SIP participant in room
  ↓
Agent worker joins room
  - Starts STT/TTS/LLM pipeline
  - Greets caller
  ↓
Conversation proceeds...
```

### Call Flow (Outbound)

```
API call to /api/v1/agent/dial
  ↓
Backend creates dispatch
  - Room: "outbound-xyz789"
  - Metadata: customer name, appointment time, phone
  ↓
Agent worker receives dispatch
  - Starts session BEFORE dialing
  ↓
Backend calls LiveKit create_sip_participant
  - Twilio dials customer via SIP trunk
  - wait_until_answered=True (blocks until pickup)
  ↓
Customer answers
  ↓
Agent greets and begins conversation
```

---

## 8. Troubleshooting

### Backend Won't Start

**Symptom**: `pydantic_core.ValidationError: Extra inputs are not permitted`

**Cause**: Missing fields in `BACKEND/config.py`

**Fix**: Ensure all env vars are declared:
```python
class Settings(BaseSettings):
    deepgram_api_key: str = ""
    elevenlabs_api_key: str = ""
    openai_api_key: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_url: str = ""
    livekit_project_id: str = ""
    livekit_sip_domain: str = ""
    sip_outbound_trunk_id: str = ""
    outbound_phone_number: str = ""
    sip_uri: str = ""
```

### Agent Worker Crash Loop

**Symptom**: `ImportError: cannot import name 'noise_cancellation'`

**Cause**: Incompatible LiveKit package versions

**Fix**: Use pinned versions in requirements.txt:
```txt
livekit-agents~=1.1.7
livekit-plugins-deepgram~=1.1.6
livekit-plugins-elevenlabs~=1.1.6
livekit-plugins-openai~=1.1.6
livekit-plugins-silero~=1.1.6
livekit-plugins-turn-detector~=1.1.6
onnxruntime>=1.18.0
```

### Pip Dependency Backtracking (Slow Build)

**Symptom**: Docker build hangs for 20+ minutes downloading package versions

**Cause**: Using `>=` constraints causes pip to test hundreds of version combinations

**Fix**: Use `~=` (compatible release) instead of `>=`:
```txt
# BAD
livekit-agents>=0.8.4

# GOOD  
livekit-agents~=1.1.7
```

### Python 3.14 Incompatibility

**Symptom**: `ERROR: No matching distribution found for onnxruntime`

**Cause**: onnxruntime (required by Silero VAD) doesn't support Python 3.14-rc yet

**Fix**: Use Python 3.11 in Dockerfile:
```dockerfile
FROM python:3.11-slim  # Not 3.14-rc
```

### No Audio on Inbound Calls

**Symptom**: Call connects but agent doesn't respond

**Cause**: Agent worker not connected to LiveKit

**Check**:
```bash
docker logs sip-agent-worker | grep "registered worker"
# Should show: registered worker id=AW_xxx url=wss://...
```

---

## 9. Deployment Modes

### Mode 1: Cloud LiveKit (Current Default)

**Use Case**: Development, quick demos, no networking complexity

**Configuration** (`.env.local`):
```bash
LIVEKIT_URL=wss://ravenhelm-gt6v1eh8.livekit.cloud
LIVEKIT_SIP_DOMAIN=ravenhelm-gt6v1eh8.pstn.livekit.cloud
```

**Start**:
```bash
docker compose up -d backend agent-worker frontend langgraph
```

**Pros**:
- ✅ No port forwarding needed
- ✅ Works from any network
- ✅ Managed infrastructure

**Cons**:
- ❌ Not on-prem (compliance issue for regulated customers)
- ❌ Requires internet

---

### Mode 2: Self-Hosted LiveKit (Enterprise/On-Prem)

**Use Case**: Customer demos, regulated deployments, air-gapped environments

**Configuration** (`.env.local`):
```bash
LIVEKIT_URL=http://livekit-local:7880
LIVEKIT_SIP_DOMAIN=YOUR_PUBLIC_IP:5060
```

**Network Requirements**:
- Public IP with UDP ports accessible
- Port forwarding: UDP 5060 (SIP), UDP 10000-10100 (RTP)

**Start**:
```bash
# Setup networking (one-time)
./scripts/setup-local-sip.sh

# Start full stack
make up-local-sip
```

**Pros**:
- ✅ Fully on-premises
- ✅ Mirrors customer deployments
- ✅ Full control over SIP/RTP

**Cons**:
- ❌ Requires port forwarding or VPS
- ❌ More complex networking

---

## 10. Key Design Decisions

### No FreeSWITCH/Asterisk Needed

**Decision**: Use LiveKit's native `livekit-sip` component instead of separate SBC

**Rationale**:
- LiveKit SIP handles signaling + RTP termination natively
- Simpler configuration (YAML vs FreeSWITCH XML)
- Native integration with LiveKit rooms/agents
- One less component to maintain/secure

**Trade-offs**:
- Must use LiveKit's SIP API (can't use arbitrary SIP features)
- Less flexibility for complex IVR routing
- Acceptable: Focus is on AI agents, not PBX features

### Agent-First Architecture

**Decision**: LiveKit agents (not raw WebRTC) for voice handling

**Rationale**:
- Built-in STT/TTS/LLM orchestration
- Turn detection, interruption handling, VAD
- Function calling integration with LangGraph
- Industry standard for voice AI

### SIP Header Context Passing

**Decision**: Pass conversation context via SIP headers during transfers

**Implementation**: Base64-encoded JSON in `X-AI-Summary` header

**Rationale**:
- Standard SIP mechanism (X- headers)
- Works across any SIP infrastructure
- Enables warm transfers with full context
- Critical for enterprise call handling

**References**: `BACKEND/utils/sip_headers.py` (to be implemented)

---

## 11. Validation Checklist

- [ ] `.env` or `.env.local` created with all credentials
- [ ] `docker compose up -d` succeeds without errors
- [ ] Backend health check passes: `curl http://localhost:8207/health`
- [ ] Agent worker shows "registered worker" in logs
- [ ] Frontend accessible: http://localhost:3207
- [ ] Agent GUI accessible: http://localhost:8207/agent/gui
- [ ] Ngrok tunnel established (for inbound testing)
- [ ] Twilio webhook configured with ngrok URL
- [ ] Test inbound call connects and agent answers
- [ ] Test outbound call via GUI or API
- [ ] (Optional) Traefik domains resolve: https://sip.ravenhelm.test

---

## 12. Common Operations

### Start Services

```bash
cd ~/Development/Quant/SIP

# Cloud mode
docker compose up -d

# Local SIP mode
make up-local-sip
```

### View Logs

```bash
# All services
docker compose logs -f

# Just agent worker
docker compose logs -f agent-worker

# Just backend
docker compose logs -f backend
```

### Restart Agent Worker

```bash
# After code changes to agent.py
docker compose restart agent-worker

# Check it reconnected
docker compose logs agent-worker | grep "registered worker"
```

### Test Outbound Call

```bash
# Via API
curl -X POST http://localhost:8207/api/v1/agent/dial \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Test Customer",
    "appointment_time": "today at 3pm",
    "phone_number": "+14155550100"
  }'

# Via GUI
open http://localhost:8207/agent/gui
```

### Monitor Call Activity

```bash
# Real-time logs
docker compose logs -f backend agent-worker | grep -E "Inbound|Outbound|transfer|participant"

# Or use Grafana (if observability stack deployed)
open https://grafana.ravenhelm.test
```

---

## 13. Security Considerations

### Twilio Webhook Validation

Add signature validation to prevent spoofed webhooks:

```python
# Install: pip install twilio
from twilio.request_validator import RequestValidator

validator = RequestValidator(os.getenv("TWILIO_AUTH_TOKEN"))

# In webhook handler:
signature = request.headers.get("X-Twilio-Signature", "")
url = str(request.url)
params = dict(await request.form())

if not validator.validate(url, params, signature):
    raise HTTPException(status_code=403, detail="Invalid signature")
```

### Environment Isolation

```bash
# Never commit .env or .env.local
git status
# Should show: working tree clean

# .gitignore already excludes:
# .env
# .env.local
# .env.*.local
```

### Production API Keys

For production deployments:
- Use OpenBao/Vault for secret storage (see RUNBOOK-010)
- Rotate keys quarterly
- Use separate keys per environment (dev/staging/prod)

---

## 14. Related Runbooks

- [RUNBOOK-001](./RUNBOOK-001-deploy-docker-service.md) — Docker service deployment patterns
- [RUNBOOK-002](./RUNBOOK-002-add-traefik-domain.md) — Traefik domain configuration
- [RUNBOOK-022](./RUNBOOK-022-configure-voice-agent.md) — Voice agent configuration (Ravenvoice)
- [RUNBOOK-024](./RUNBOOK-024-add-shared-service.md) — Add new shared service
- [RUNBOOK-026](./RUNBOOK-026-m2c-demo-integration.md) — Port registry integration example

---

## 15. Next Steps

### Week 1: Enterprise Call Patterns

Implement intelligent call handling capabilities:

1. **Warm Transfer with Context** - Pass conversation transcript via SIP headers
2. **Supervisor Observation** - Silent monitoring mode
3. **Hold Music** - Background audio during lookups
4. **Multi-Agent Orchestration** - Tier-1 → Tier-2 escalation via LangGraph

See `~/Development/Quant/SIP/docs/ENTERPRISE_CALL_PATTERNS.md` (to be created as follow-on runbook)

### Week 2: CCaaS Integration

Build adapter framework for contact center platforms:

1. **AudioHook Protocol Handler** - Universal WebSocket handler
2. **Genesys Cloud Adapter** - Reference implementation
3. **Five9/Nice/Amazon Adapters** - Follow template pattern
4. **Integration Playbook** - Repeatable 30-minute onboarding

See `~/Development/Quant/SIP/docs/CCAAS_INTEGRATION.md` (to be created as RUNBOOK-028)

---

## Tags

`voice`, `sip`, `telephony`, `livekit`, `agents`, `work`, `alfheim`

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2025-12-04 | Norns/Cursor | Initial runbook creation for SIP platform |

---

*"From voice comes understanding, from understanding comes action."*


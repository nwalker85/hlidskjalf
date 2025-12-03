# The Ravenhelm Platform

> *The ravens still fly. They still return with what is seen and what is known.*

A cognitive infrastructure platform for enterprise AI systems. This is not "a chatbot runner" or "an agent framework" — this is the foundation for systems that **perceive**, **remember**, and **understand**.

---

## The Ravens by Another Name

There is an old story about a one-eyed god who sends two ravens into the world each day:

- **Huginn** brings what is happening **now** — thought, perception, the shape of the present
- **Muninn** brings what has **happened before** — memory, pattern, the shape of meaning

In this architecture, the ravens have new names. But their purposes have not changed.

| Raven | Role | Technology | Domain |
|-------|------|------------|--------|
| **Huginn** | State Manager | NATS JetStream + Redis | ms → minutes (perception) |
| **Muninn** | Memory Manager | Redpanda + PostgreSQL/pgvector | days → forever (knowledge) |

A system with only Huginn is reactive but forgetful.  
A system with only Muninn is knowledgeable but slow.  
A system with neither is what today's LLM tools mostly are.  
A system with **both** is *cognitive*.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ravenhelm-proxy (:443)                              │
│                    *.ravenhelm.test → 127.0.0.1                             │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ├── *.saaa.ravenhelm.test        → :8443   Service as an Agent
        ├── *.agentcrucible.ravenhelm.test → :9443  Agent Crucible
        ├── *.gitlab.ravenhelm.test      → :11443  GitLab + Registry
        ├── *.observe.ravenhelm.test     → :12443  Observability Stack
        ├── *.events.ravenhelm.test      → :13443  Event Plane (Redpanda)
        └── vault.ravenhelm.test         → :14443  Secrets (OpenBao)

┌─────────────────────────────────────────────────────────────────────────────┐
│                           SHARED SERVICES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  HUGINN (State)              MUNINN (Memory)           DOMAIN KNOWLEDGE     │
│  ━━━━━━━━━━━━━━━             ━━━━━━━━━━━━━━━           ━━━━━━━━━━━━━━━━━    │
│  ┌─────────────┐             ┌─────────────┐           ┌─────────────┐      │
│  │    NATS     │             │  Redpanda   │           │  LocalStack │      │
│  │  JetStream  │             │  (Kafka)    │           │    (AWS)    │      │
│  │   :4222     │             │   :19092    │           │   :4566     │      │
│  └──────┬──────┘             └──────┬──────┘           └─────────────┘      │
│         │                           │                                       │
│         ▼                           ▼                                       │
│  ┌─────────────┐             ┌─────────────┐           ┌─────────────┐      │
│  │    Redis    │             │  PostgreSQL │           │   OpenBao   │      │
│  │  (L1 cache) │             │  + pgvector │           │   (Vault)   │      │
│  │   :6379     │             │   :5432     │           │   :8200     │      │
│  └─────────────┘             └─────────────┘           └─────────────┘      │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                           OBSERVABILITY                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  INFRASTRUCTURE              LLM OBSERVABILITY                              │
│  ━━━━━━━━━━━━━━━             ━━━━━━━━━━━━━━━━                               │
│  ┌─────────────┐             ┌─────────────┐                                │
│  │    OTEL     │────────────▶│  LangFuse   │  langfuse.observe.ravenhelm   │
│  │  Collector  │             │   :3001     │  (LangGraph/LangChain traces) │
│  │ :4317/:4318 │             └─────────────┘                                │
│  └──────┬──────┘             ┌─────────────┐                                │
│         │                    │   Phoenix   │  phoenix.observe.ravenhelm    │
│         ├──────▶ Tempo       │   :6006     │  (Embeddings/RAG debugging)   │
│         ├──────▶ Prometheus  └─────────────┘                                │
│         └──────▶ Loki                                                       │
│                    │                                                        │
│                    ▼                                                        │
│             ┌─────────────┐                                                 │
│             │   Grafana   │  grafana.observe.ravenhelm.test                │
│             │   :3000     │                                                 │
│             └─────────────┘                                                 │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                      VOICE & REAL-TIME (Skalds)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LIVEKIT (WebRTC)            LOCAL LLM               EXTERNAL APIS          │
│  ━━━━━━━━━━━━━━━━            ━━━━━━━━━               ━━━━━━━━━━━━━━         │
│  ┌─────────────┐             ┌─────────────┐         ┌─────────────┐        │
│  │   LiveKit   │◀───────────▶│   Ollama    │         │  Deepgram   │        │
│  │   Server    │  Audio/LLM  │   :11434    │         │    (STT)    │        │
│  │   :7880     │             └─────────────┘         └─────────────┘        │
│  └─────────────┘                                     ┌─────────────┐        │
│        │                                             │ ElevenLabs  │        │
│        └─────────────── Voice Agents ───────────────▶│    (TTS)    │        │
│                                                      └─────────────┘        │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                            DEVOPS                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐             ┌─────────────┐                                │
│  │   GitLab    │             │   GitLab    │                                │
│  │     CE      │             │   Runner    │                                │
│  │   :11443    │             │             │                                │
│  └─────────────┘             └─────────────┘                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Docker Desktop with 8GB+ RAM allocated
- dnsmasq configured for `*.ravenhelm.test` → `127.0.0.1`
- Ravenhelm CA trusted in macOS Keychain
- mkcert (`brew install mkcert nss`) for generating trusted development certificates

### Generate Dev Certificates (mkcert)

Issue a wildcard certificate once, then reuse it across `ravenhelm-proxy`, `observability`, `vault`, and any other nginx sidecars that mount `config/certs`.

```bash
brew install mkcert nss   # once
mkcert -install           # trusts the Ravenhelm Dev CA locally

cd ravenhelm-proxy/config/certs
mkcert -cert-file server.crt -key-file server.key \
  ravenhelm.test \
  "*.ravenhelm.test" \
  "*.observe.ravenhelm.test" \
  "*.events.ravenhelm.test" \
  vault.ravenhelm.test \
  localstack.ravenhelm.test \
  "*.saaa.ravenhelm.test" \
  "*.agentcrucible.ravenhelm.test"

# copy/share as needed
cp server.crt server.key ../../config/certs/
```

Re-run `mkcert` whenever you add new subdomains; the command can be repeated safely and will overwrite the cert pair in place. Mkcert also installs the CA into the System keychain, so browsers trust the domains immediately.

### 1. Start the Platform

```bash
# Start ravenhelm-proxy first (if not running)
cd ravenhelm-proxy && docker compose up -d && cd ..

# Start all platform services
docker compose up -d

# Watch startup (GitLab takes 3-5 minutes)
docker compose logs -f
```

### 2. Access Services

> **Note**: Services are accessible via Traefik proxy on port 8443 (e.g., `https://norns.ravenhelm.test:8443`)

| Service | URL | Purpose |
|---------|-----|---------|
| **Norns Chat** | https://hlidskjalf.ravenhelm.test:8443 | AI Agent Interface |
| **Norns API** | https://norns.ravenhelm.test:8443 | LangGraph API |
| **Ollama** | https://ollama.ravenhelm.test:8443 | Local LLM (llama3.1) |
| **Grafana** | https://grafana.observe.ravenhelm.test:8443 | Dashboards |
| **LangFuse** | https://langfuse.observe.ravenhelm.test:8443 | LLM Traces |
| **Phoenix** | https://phoenix.observe.ravenhelm.test:8443 | RAG Debug |
| **Redpanda** | https://events.ravenhelm.test:8443 | Event Console |
| **Vault** | https://vault.ravenhelm.test:8443 | Secrets |
| **Memgraph** | https://memgraph.ravenhelm.test:8443 | Graph DB |
| **Neo4j** | https://neo4j.ravenhelm.test:8443 | Knowledge Graph |

### 3. Get GitLab Root Password

```bash
docker compose exec gitlab grep 'Password:' /etc/gitlab/initial_root_password
```

---

## Projects

### `templates/ravenmaskos/` — Boilerplate Template

Production-ready FastAPI + Next.js template with:

- **Backend**: FastAPI, PostgreSQL, Redis, Kafka, OTEL
- **Frontend**: Next.js, shadcn/ui, React Query
- **Auth**: Zitadel OIDC + OpenFGA ReBAC
- **Infra**: Kubernetes manifests, Terraform modules
- **Cognitive**: Huginn (NATS) + Muninn (Kafka/pgvector) config

Clone from GitLab to start new projects.

### `tests/saaa-tests/` — Testing Suite

Comprehensive testing framework:

- **Governance**: BIPA compliance, PII redaction (DeepEval)
- **Latency**: Agent tool call budgets, streaming first token
- **Load**: Locust-based stress testing
- **Voice**: Audio pipeline testing
- **E2E**: Playwright frontend testing

Supports both `local` and `ravenhelm` deployment modes.

### `ravenhelm-proxy/` — Edge Gateway

Central reverse proxy for all `*.ravenhelm.test` domains:

- SSL termination with wildcard certificates
- WebSocket support
- LiveKit WebRTC passthrough

---

## Services Reference

### Cognitive Layer

| Service | Port | Purpose |
|---------|------|---------|
| **NATS JetStream** | 4222 | Huginn: Real-time state transport |
| **Redis** | 6379 | Huginn: L1 cache, session state |
| **Redpanda** | 19092 | Muninn: Durable event streaming |
| **PostgreSQL + pgvector** | 5432 | Muninn: Memory storage + vector search |

### Observability

| Service | Port | Purpose |
|---------|------|---------|
| **OTEL Collector** | 4317/4318 | Telemetry ingestion (gRPC/HTTP) |
| **Prometheus** | 9090 | Metrics storage |
| **Loki** | 3100 | Log aggregation |
| **Tempo** | 3200 | Distributed tracing |
| **Grafana** | 3000 | Dashboards |
| **Alertmanager** | 9093 | Alert routing |
| **LangFuse** | 3001 | LLM observability |
| **Phoenix** | 6006 | Embeddings/RAG debugging |

### Voice & Real-Time (Skalds)

| Service | Port | Purpose |
|---------|------|---------|
| **LiveKit** | 7880 | WebRTC server (voice agents) |
| **LiveKit RTC** | 7881-7892 | RTC/UDP media ports |
| **Ollama** | 11434 | Local LLM (llama3.1, embeddings) |

> **Note:** Voice agents use LiveKit for real-time audio, with Deepgram (STT) and ElevenLabs (TTS) 
> as external services. See `libs/ravenvoice/` for the reusable voice integration library.

### DevOps

| Service | Port | Purpose |
|---------|------|---------|
| **GitLab CE** | 11443 | Source control, CI/CD |
| **GitLab Runner** | - | Docker executor |
| **LocalStack** | 4566 | AWS emulation |
| **OpenBao** | 8200 | Secrets management |

---

## Muninn Schema

The Memory Manager uses PostgreSQL + pgvector for long-term knowledge:

```sql
-- Episodic memories (user-specific experiences)
muninn.episodic_memories
  - user_id, session_id, agent_id
  - content, embedding (vector 1536)
  - importance_score, access_count
  - expires_at

-- Semantic memories (generalized knowledge)
muninn.semantic_memories
  - domain, content, embedding
  - confidence_score
  - source_episodic_ids (promotion tracking)

-- Procedural memories (skills, workflows)
muninn.procedural_memories
  - name, steps (JSONB)
  - success_rate, execution_count

-- Memory candidates (staging for promotion)
muninn.memory_candidates
  - source_type, content, embedding
  - promotion_score, promoted_to_id
```

---

## LocalStack Resources

Pre-configured AWS services via LocalStack:

```bash
# Secrets Manager
awslocal secretsmanager list-secrets

# SSM Parameters
awslocal ssm get-parameters-by-path --path /ravenhelm/dev --recursive

# S3 Buckets
awslocal s3 ls

# SQS Queues
awslocal sqs list-queues
```

---

## Bootstrap Scripts

### LocalStack

`./localstack/init/init-aws.sh` seeds Secrets Manager, SSM, S3, and SQS resources after LocalStack reports healthy. Run it any time you need to recreate dev infrastructure:

```bash
./localstack/init/init-aws.sh
```


---

## Deployment Modes

### Local Development (Default)

Docker Compose for fast iteration on your laptop:

```bash
docker compose up -d
```

### Shared Mode (Ravenhelm Platform)

Projects connect to central platform services via Docker network names:

```env
DEPLOYMENT_MODE=shared
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/myapp
REDIS_URL=redis://redis:6379/0
KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
NATS_URL=nats://nats:4222
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
LANGFUSE_HOST=https://langfuse.observe.ravenhelm.test:8443
```

> **Note:** Use Docker service names (postgres, redis, redpanda) for containers.  
> Use `*.ravenhelm.test:8443` domains for browser/external access.

---

## Documentation & Wiki Workflow

### 1. Author in the Repo First
- **Architecture / strategy docs** live under `docs/` and are orchestrated via `docs/KNOWLEDGE_AND_PROCESS.md`.
- **Runbooks** belong in `docs/runbooks/` (follow the RUNBOOK-### naming convention and include tags/frontmatter).
- **Tables for the wiki** are generated in `docs/wiki/` (e.g., `Architecture_Index.md`, `Runbook_Catalog.md`). Update these whenever you change the source docs so we keep the SoT inside the repo.

### 2. Push to the GitLab Wiki
```bash
# 1. Clone the wiki repo
cd /Users/nwalker/Development
git clone https://oauth2:<token>@gitlab.ravenhelm.test/ravenhelm/hlidskjalf.wiki.git hlidskjalf-wiki

# 2. Copy rendered files from docs/wiki
cp ./hlidskjalf/docs/wiki/*.md ./hlidskjalf-wiki/

# 3. Commit & push
cd hlidskjalf-wiki
git config user.name  "Ravenhelm Platform Bot"
git config user.email "bot@ravenhelm.test"
git add .
git commit -m "Sync wiki tables"
git push origin main
```

Or automate it:

```bash
export GITLAB_TOKEN=glpat-...
./scripts/sync_wiki.sh
```

### 3. Runbook Updates
1. Add or edit the relevant `docs/runbooks/RUNBOOK-XXX-*.md` file.
2. Reflect the change in `docs/wiki/Runbook_Catalog.md` (tags, prerequisites, TODOs).
3. Open/close an issue on the Operations Board (see next section) so the update is tracked.

---

## Operations Board Workflow

| Label | Meaning | When to use |
|-------|---------|-------------|
| `status::backlog` | Idea or request not yet prioritized | New work items, open questions |
| `status::ready` | Groomed and ready for assignment | After acceptance criteria are defined |
| `status::in-progress` | Actively being executed | Once you start the task (including wiki/runbook edits) |
| `status::review` | Needs verification/PR review | After MR open but before merge |
| `status::done` | Verified complete | When merged/deployed/documented |
| `status::blocked` | Waiting on external dependency | Cert issues, missing approvals, upstream bugs |

### Create/Update Issues
```bash
# Example: create an issue for a new runbook
curl -s -X POST \
  -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "title": "Runbook: Configure New Voice Agent",
        "description": "Document the LiveKit + Deepgram steps...",
        "labels": "wiki,status::backlog" }' \
  https://gitlab.ravenhelm.test/api/v4/projects/2/issues
```

### Moving Cards
Use the GitLab UI (`Issues → Boards → Operations Board`) or script it:
```bash
# Move issue IID 12 to in-progress
curl -s -X PUT \
  -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "add_labels": "status::in-progress",
        "remove_labels": "status::ready" }' \
  https://gitlab.ravenhelm.test/api/v4/projects/2/issues/12
```

Automation helper:

```bash
export GITLAB_TOKEN=glpat-...
./scripts/ops_board.py list --labels wiki
./scripts/ops_board.py create --title "Wiki: Add compliance section" --labels wiki status::backlog
./scripts/ops_board.py move --iid 12 --add status::in-progress --remove status::ready
```

### Good Citizenship
- Every documentation or operational change **must** have a corresponding issue.
- Keep descriptions updated with links to PRs, runbooks, or wiki pages.
- Close the issue (label `status::done`) only after wiki/runbook updates are merged and pushed.

---

## Future: Production & SaaS Deployment

### The Target Architecture

Ravenhelm is designed to be deployed as a **multi-tenant SaaS platform** on AWS, and to **generate enterprise projects** that also deploy to Kubernetes.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RAVENHELM SaaS (EKS)                              │
│                   Your platform, deployed to AWS                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────────────────────────────────────────────────┐          │
│   │                    Hliðskjálf UI                          │          │
│   │              + Norns AI (Project Factory)                 │          │
│   └──────────────────────────────────────────────────────────┘          │
│                              │                                           │
│                              │ "Create new project"                      │
│                              ▼                                           │
│   ┌──────────────────────────────────────────────────────────┐          │
│   │           GENERATED ENTERPRISE PROJECT                    │          │
│   │  ┌─────────────────────────────────────────────────────┐ │          │
│   │  │  Terraform (EKS, RDS, S3, etc.)                     │ │          │
│   │  │  Helm Charts (K8s manifests)                        │ │          │
│   │  │  GitLab CI/CD Pipeline                              │ │          │
│   │  │  SPIRE/Zitadel integration                          │ │          │
│   │  └─────────────────────────────────────────────────────┘ │          │
│   └──────────────────────────────────────────────────────────┘          │
│                              │                                           │
│                              │ Deploys to customer AWS                   │
│                              ▼                                           │
│   ┌──────────────────────────────────────────────────────────┐          │
│   │              CUSTOMER'S AWS ACCOUNT (EKS)                │          │
│   │         Enterprise-grade Kubernetes deployment           │          │
│   └──────────────────────────────────────────────────────────┘          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Kubernetes?

| Local Dev | Production |
|-----------|------------|
| Docker Compose | EKS (Kubernetes) |
| SPIRE + spiffe-helper | Istio service mesh (automatic mTLS) |
| Manual volume ownership | Native fsGroup |
| Single node | Auto-scaling, self-healing |

### The Development Flow

```
LOCAL (Docker Compose)
  │ Fast iteration, debugging
  │
  ▼ git push
CI/CD (GitLab)
  │ Build images, test with `kind`, deploy Helm
  │
  ▼ ArgoCD
PRODUCTION (EKS)
  │ Istio mTLS, HPA scaling, native secrets
```

### Generated Project Stack

The `ravenmaskos` template will generate:

```
<project>/
├── terraform/
│   ├── modules/
│   │   ├── eks/           # EKS cluster
│   │   ├── rds/           # PostgreSQL
│   │   ├── elasticache/   # Redis
│   │   └── ...
│   └── environments/
│       ├── dev/
│       ├── staging/
│       └── prod/
├── helm/
│   └── <project-name>/
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           └── ingress.yaml
├── .gitlab-ci.yml         # Terraform + Helm pipeline
└── docker-compose.yml     # Local dev only
```

### Platform User Standard

All platform services run as a standardized user for consistent file ownership:

```
User: ravenhelm
UID:  1001
GID:  1001
```

This maps to Kubernetes `fsGroup: 1001` for seamless local-to-production parity.

---

## Troubleshooting

### GitLab won't start

```bash
# Check logs
docker compose logs gitlab --tail 100

# GitLab needs 4-6GB RAM. Check Docker Desktop resources.
```

### Certificate errors

```bash
# Ensure CA is trusted
security dump-trust-settings -d | grep -A10 "Ravenhelm"

# Regenerate certs if needed (see ravenhelm-proxy/README.md)
```

### DNS not resolving

```bash
# Check dnsmasq
dig frontend.saaa.ravenhelm.test @127.0.0.1 -p 15353 +short

# Should return: 127.0.0.1
```

### Reset everything

```bash
docker compose down -v  # ⚠️ Destroys all data
docker compose up -d
```

## Twilio Paging (optional)

The Norns can page you via SMS/MMS using Twilio. Populate the following keys in your `.env` (or your secret store) and restart the FastAPI service:

```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+15555550100        # omit if you only use a messaging service
TWILIO_MESSAGING_SERVICE_SID=MGxxxxxxxxxxxxxxxxxxx # optional but preferred
```

- Provide at least one of `TWILIO_FROM_NUMBER` or `TWILIO_MESSAGING_SERVICE_SID`.
- All phone numbers must be E.164 formatted (`+1...`).
- Once configured, the `send_twilio_message` tool becomes available to the Norns/Deep Agent so they can notify Odin whenever incidents or deployment milestones occur.

## Norns Agent Chat UI + Deep Agent

The LangGraph Agent Chat UI is accessible at `https://hlidskjalf.ravenhelm.test:8443/norns`. It provides:
- Tool visualization
- Thread history and checkpoints
- Cognitive memory integration (Huginn, Muninn, Mímir)

### Configuration

All configuration uses `*.ravenhelm.test` domains via Traefik proxy:

**UI Environment (`hlidskjalf/ui/.env.local`):**
```env
NEXT_PUBLIC_API_URL=https://hlidskjalf-api.ravenhelm.test:8443
NEXT_PUBLIC_LANGGRAPH_API_URL=https://norns.ravenhelm.test:8443
NEXT_PUBLIC_LANGGRAPH_ASSISTANT_ID=norns
LANGGRAPH_API_URL=http://langgraph:2024  # Internal Docker network
```

**Backend Environment (`.env`):**
```env
NORNS_GRAPH_API_URL=https://norns.ravenhelm.test:8443
NORNS_GRAPH_ASSISTANT_ID=norns
REDIS_URL=redis://redis:6379/1
REDIS_MEMORY_TTL_SECONDS=3600
REDIS_MEMORY_PREFIX=norns
```

### Running with Docker Compose

The entire stack launches with Docker Compose:

```bash
# Start all services (includes LangGraph server)
docker compose up -d

# Access Norns UI
open https://hlidskjalf.ravenhelm.test:8443/norns
```

### Deep Agent Tools

The Norns have access to:
- **Memory tools**: `huginn_perceive`, `muninn_recall`, `frigg_divine`, `mimir_consult`
- **Workspace tools**: `workspace_list`, `workspace_read`, `workspace_write`
- **Agent tools**: `spawn_subagent`, `write_todos`
- **Platform tools**: `execute_terminal_command`, `read_file`, etc.

---

## The Cognitive Spine

This platform exists to make AI systems that are not merely reactive, but **aware**.

- **Huginn** ensures the system never hesitates
- **Muninn** ensures the system never forgets what matters
- **Domain Knowledge** ensures the system never hallucinates what is false
- **The Event Fabric** ensures the system never stalls

This is the architecture of a mind.

---

*"The ravens still fly."*

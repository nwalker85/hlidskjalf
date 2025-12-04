# Ravenhelm Platform - Project Plan

> **A secure, repeatable, scalable development and deployment platform**

---

## The Vision

Build a **secure foundation first**, then layer everything else on top:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SECURITY FIRST                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    LAYER 4: APPLICATION                                                      │
│    ┌────────────────────────────────────────────────────────────────────┐   │
│    │  Norns AI  │  Hliðskjálf UI  │  Your Projects  │  Voice/Chat      │   │
│    └────────────────────────────────────────────────────────────────────┘   │
│                              ▲                                               │
│    LAYER 3: AUTHENTICATION   │  OAuth 2.1 / OIDC (Zitadel)                  │
│    ┌────────────────────────────────────────────────────────────────────┐   │
│    │  SSO for all UIs  │  Service Accounts  │  MCP OAuth  │  JWT        │   │
│    └────────────────────────────────────────────────────────────────────┘   │
│                              ▲                                               │
│    LAYER 2: TRANSPORT        │  mTLS (SPIRE SVIDs)                          │
│    ┌────────────────────────────────────────────────────────────────────┐   │
│    │  Encrypted service-to-service  │  Workload identity  │  Zero Trust │   │
│    └────────────────────────────────────────────────────────────────────┘   │
│                              ▲                                               │
│    LAYER 1: STORAGE          │  Encryption at Rest                          │
│    ┌────────────────────────────────────────────────────────────────────┐   │
│    │  PostgreSQL TDE  │  Redis AUTH  │  Kafka TLS  │  OpenBao Secrets   │   │
│    └────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Security Architecture

### Layer 1: Encryption at Rest

| Service | Encryption Method | Status |
|---------|-------------------|--------|
| PostgreSQL | TDE with encrypted volumes | ⏳ Configure |
| Redis | AUTH + encrypted volumes | ⏳ Configure |
| Redpanda/Kafka | TLS + encrypted volumes | ⏳ Configure |
| OpenBao | Auto-unseal + encrypted | ⏳ Configure |
| Docker Volumes | LUKS encryption | ⏳ Configure |

### Layer 2: mTLS (SPIRE)

Every service gets a cryptographic identity (SVID) and all service-to-service communication is encrypted and authenticated.

| Component | SPIFFE ID | Status |
|-----------|-----------|--------|
| SPIRE Server | `spiffe://ravenhelm.local/server` | ✅ Running |
| SPIRE Agent | `spiffe://ravenhelm.local/agent/local` | ✅ Running |
| PostgreSQL | `spiffe://ravenhelm.local/workload/postgres` | ✅ TLS Enabled |
| Redis | `spiffe://ravenhelm.local/workload/redis` | ✅ TLS Enabled |
| NATS | `spiffe://ravenhelm.local/workload/nats` | ✅ TLS Enabled |
| Redpanda | `spiffe://ravenhelm.local/workload/redpanda` | ⏳ Register |
| Grafana | `spiffe://ravenhelm.local/workload/grafana` | ⏳ Register |
| LangFuse | `spiffe://ravenhelm.local/workload/langfuse` | ⏳ Register |
| Hliðskjálf | `spiffe://ravenhelm.local/workload/control-plane` | ⏳ Register |
| Norns/LangGraph | `spiffe://ravenhelm.local/workload/norns` | ⏳ Register |

### Layer 3: Authentication (Zitadel)

All human access goes through Zitadel SSO. All machine access uses OAuth 2.1.

| Access Type | Method | Status |
|-------------|--------|--------|
| UI Access | OIDC SSO via Zitadel | ⏳ Deploy Zitadel |
| MCP Tools | OAuth 2.1 client credentials | ⏳ Configure |
| API Access | JWT bearer tokens | ⏳ Configure |
| Norns Agent | Service account + mTLS | ⏳ Configure |

### Layer 4: Application Security

| Control | Implementation | Status |
|---------|----------------|--------|
| Input validation | Pydantic models | ✅ |
| Rate limiting | Redis-backed | ⏳ |
| Audit logging | OTEL + Loki | ✅ Partial |
| Secret management | OpenBao | ⏳ |

---

## Phased Implementation

### Phase 0: Zero Trust Foundation ✅ COMPLETE
**Goal:** SPIRE running, all workloads registered, TLS enabled, standardized ownership

| Task | Priority | Status |
|------|----------|--------|
| Generate SPIRE upstream CA | 🔴 | ✅ |
| Start SPIRE server | 🔴 | ✅ |
| Start SPIRE agent | 🔴 | ✅ |
| Register all workloads | 🔴 | ✅ |
| Enable TLS on NATS | 🔴 | ✅ |
| Enable TLS on PostgreSQL | 🔴 | ✅ |
| Enable TLS on Redis | 🔴 | ✅ |
| Create RUNBOOK-004 for SPIRE | 🔴 | ✅ |
| Document trust domain | 🟡 | ✅ |
| Standardize platform user (ravenhelm:1001:1001) | 🔴 | ✅ |
| Update services to run as ravenhelm user | 🔴 | ✅ |
| Create volume initialization script | 🟡 | ✅ |
| Create RUNBOOK-005 for file ownership | 🟡 | ✅ |

### Phase 1: Identity & SSO (WEEK 2) ✅ COMPLETE
**Goal:** Zitadel deployed, all UIs behind SSO

| Task | Priority | Status |
|------|----------|--------|
| Deploy Zitadel | 🔴 | ✅ |
| Bootstrap Zitadel (admin, projects, roles) | 🔴 | ✅ |
| Configure Grafana OIDC | 🔴 | ✅ Verified |
| Configure GitLab OIDC | 🔴 | ✅ Verified |
| Configure Hliðskjálf OIDC | 🔴 | ✅ Verified |
| Configure LangFuse OIDC | 🟡 | ✅ Verified |
| Configure Redpanda Console OIDC | 🟡 | ✅ Verified |
| Create Norns service account | 🔴 | ✅ |
| Configure MCP OAuth 2.1 | 🟡 | ⏳ Deferred to Phase 5 |
| Create RUNBOOK-006 for Zitadel | 🔴 | ✅ |
| Create RUNBOOK-009 for GitLab SSO | 🔴 | ✅ |

**Notes:**
- All SSO logins verified working via browser (Dec 3, 2025)
- LangFuse route fixed: `langfuse.ravenhelm.test` added to Traefik
- Hliðskjálf using NextAuth.js with Zitadel provider

### Phase 2: Secrets & Encryption (WEEK 3) ✅ COMPLETE
**Goal:** All secrets in Secrets Manager, storage encrypted

**Architecture Decision:** LocalStack (AWS Secrets Manager API) instead of OpenBao
- Provides dev/prod parity for AWS deployment
- S3 for artifact storage, backups, logs
- KMS for encryption key management
- OpenBao deferred (can be enabled later for advanced Vault features)

| Task | Priority | Status |
|------|----------|--------|
| Configure LocalStack persistence | 🔴 | ✅ |
| Migrate secrets to Secrets Manager | 🔴 | ✅ |
| Create Python SecretsClient | 🔴 | ✅ |
| Configure S3 buckets | 🔴 | ✅ |
| Enable Redis AUTH | 🟡 | ✅ |
| Store PostgreSQL credentials | 🟡 | ✅ |
| Create backup-to-S3 script | 🟡 | ✅ |
| Document secret rotation (RUNBOOK-010) | 🟡 | ✅ |

### Phase 3: Proxy & Routing (WEEK 4) ✅ COMPLETE
**Goal:** Traefik with TLS termination and auth middleware - ZERO TRUST DEPLOYED

| Task | Priority | Status |
|------|----------|--------|
| Deploy Traefik | 🔴 | ✅ |
| Configure TLS termination | 🔴 | ✅ |
| Deploy oauth2-proxy | 🔴 | ✅ |
| Configure Traefik forwardAuth middleware | 🔴 | ✅ |
| Apply zero-trust to internal services | 🔴 | ✅ |
| Migrate from nginx | 🔴 | ✅ |
| Test all endpoints | 🟡 | ✅ |

**Zero-Trust Access Control:**
- **PUBLIC (no auth):** `zitadel.ravenhelm.test`, `auth.ravenhelm.test`
- **Native SSO:** Grafana, GitLab, LangFuse, Hliðskjálf UI, Redpanda Console
- **Forward Auth (protected):** Prometheus, Loki, Tempo, Alertmanager, Alloy, Phoenix, Vault, LocalStack, n8n, NATS, SPIRE, LiveKit, RAG services, Graph DBs

### Phase 4: Core Workflow (WEEK 5)
**Goal:** Secure project creation and deployment

| Task | Priority | Status |
|------|----------|--------|
| Deploy GitLab CE | 🔴 | ✅ |
| Configure GitLab SSO | 🔴 | ✅ |
| Create Ravenhelm Organization | 🔴 | ✅ |
| Create Ravenhelm Group | 🔴 | ✅ |
| Set up admin user | 🔴 | ✅ |
| Generate GitLab API token | 🟡 | ⏳ |
| **MCP Shared Services Tool – Phase 4A** | 🔴 | ✅ |
| ↳ Research MCP protocol & best practices | 🟢 | ✅ Dec 3 |
| ↳ Architect multi-service MCP server | 🟢 | ✅ Dec 3 |
| ↳ Build GitLab MCP tools (projects, runners, knowledge read) | 🟢 | ✅ (see `services/mcp-server-gitlab/`) |
| ↳ Build Zitadel MCP tools | 🔴 | ✅ Dec 4 |
| ↳ Build Docker MCP tools | 🟡 | ✅ Dec 4 |
| ↳ Test MCP server integration (Traefik + SPIRE mTLS) | 🟢 | ✅ (`mcp.gitlab.ravenhelm.test`) |
| ↳ UAT with Norns agent | 🟡 | ⏳ |
| Implement Zitadel→GitLab permission sync | 🟡 | ⏳ |
| Import ravenmaskos template | 🔴 | ⏳ |
| Configure AWS credentials in Vault | 🔴 | ⏳ |
| Test Terraform deployment | 🟡 | ⏳ |
| Automate wiki + Operations Board workflows (`scripts/sync_wiki.sh`, `scripts/ops_board.py`) | 🟡 | ✅ |

### Phase 5: Advanced Features (WEEK 6+)
**Goal:** Voice, chat, observability

| Task | Priority | Status |
|------|----------|--------|
| LiveKit with mTLS | 🟡 | ⏳ |
| SIP Voice AI Platform (`~/Development/Quant/SIP`) | 🔴 | ✅ **Active Development** |
| ├─ LiveKit agent worker (outbound calling) | 🔴 | ✅ |
| ├─ Inbound SIP webhook handler | 🔴 | ✅ |
| ├─ Agent control GUI | 🟡 | ✅ |
| ├─ Port registry integration (8207, 3207, 8208) | 🔴 | ✅ |
| ├─ Traefik routing (sip.ravenhelm.test) | 🔴 | ✅ |
| ├─ RUNBOOK-027 created | 🔴 | ✅ |
| └─ Twilio API integration | 🟡 | ✅ |
| Bifrost with OAuth | 🟡 | ⏳ |
| Cost tracking | 🟡 | ⏳ |
| Audit dashboards | 🟡 | ⏳ |

**SIP Platform Status** (as of 2025-12-04):
- Project path: `/Users/nwalker/Development/Quant/SIP`
- Running: Backend (8207), Frontend (3207), LangGraph (8208), Agent Worker
- Deployment mode: Cloud LiveKit (development)
- Ready for: Inbound/outbound calling, warm transfer implementation
- Next: Enterprise call escalation patterns (Week 1 priority)

### Phase 6: Monitoring, Alerting & Self-Healing (WEEK 7+)
**Goal:** Automated incident detection, AI-driven triage, self-healing

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MONITORING, ALERTING & SELF-HEALING                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    DETECTION LAYER                                                           │
│    ┌────────────────────────────────────────────────────────────────────┐   │
│    │  Prometheus   │  Grafana Alloy  │  Docker Healthchecks  │  Autoheal│   │
│    │  (metrics)    │  (logs/traces)  │  (container health)   │  (restart)│  │
│    └────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│    ROUTING LAYER             ▼  AlertManager webhook                        │
│    ┌────────────────────────────────────────────────────────────────────┐   │
│    │                      Bifrost Gateway                                │   │
│    │                    /api/alerts/ingest                               │   │
│    └────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│    INTELLIGENCE LAYER        ▼                                              │
│    ┌────────────────────────────────────────────────────────────────────┐   │
│    │                       Norns AI Agent                                │   │
│    │                    (On-Call First Responder)                        │   │
│    │  • Correlate alerts with recent changes                            │   │
│    │  • Query logs/traces for root cause                                │   │
│    │  • Attempt automated remediation                                   │   │
│    │  • Escalate to humans only if auto-fix fails                       │   │
│    └────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│    ACTION LAYER              ▼                                              │
│    ┌──────────┬──────────┬──────────┬──────────┬──────────┐              │
│    │ Restart  │  Scale   │ Rollback │  Notify  │ Escalate │              │
│    │Container │ Service  │  Deploy  │ Channel  │  Human   │              │
│    └──────────┴──────────┴──────────┴──────────┴──────────┘              │
│                                       │                                     │
│    NOTIFICATION LAYER                 ▼  (via Bifrost adapters)            │
│    ┌──────────┬──────────┬──────────┬──────────┬──────────┐              │
│    │  Slack   │ Telegram │ Discord  │PagerDuty │  Email   │              │
│    └──────────┴──────────┴──────────┴──────────┴──────────┘              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

| Task | Priority | Status |
|------|----------|--------|
| Add Autoheal container | 🔴 | ⏳ |
| Create Prometheus alert rules | 🔴 | ⏳ |
| Add Bifrost alert webhook endpoint | 🔴 | ⏳ |
| Create Norns alert handler agent | 🔴 | ⏳ |
| Configure Alertmanager → Bifrost | 🔴 | ⏳ |
| Add Docker API access for Norns | 🟡 | ⏳ |
| Create remediation MCP tools | 🟡 | ⏳ |
| Add notification adapters (Slack, etc) | 🟡 | ⏳ |
| Create incident audit logging | 🟡 | ⏳ |
| RUNBOOK-008: Alert Response | 🟡 | ⏳ |

**Alert Rules (per Enterprise Scaffold):**
- `ServiceDown`: up == 0 for 1m → critical
- `HighErrorRate`: 5xx rate > 1% for 5m → critical
- `HighLatency`: p95 > 2500ms for 5m → critical
- `HighCPU`: > 80% for 10m → warning
- `HighMemory`: > 80% for 10m → warning
- `ContainerRestarting`: > 3 restarts/hour → warning

**Norns On-Call Capabilities:**
- Restart unhealthy containers (escalate after 3 failures)
- Clear caches on high memory
- Query recent deploys on high error rate
- Kill idle database connections
- Document all actions in audit log

---

## SPIRE Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SPIRE ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    TRUST DOMAIN: ravenhelm.local                                            │
│                                                                              │
│    ┌─────────────────────┐                                                  │
│    │    SPIRE Server     │  Port 8081                                       │
│    │  (Certificate Auth) │  Issues SVIDs to registered workloads            │
│    └──────────┬──────────┘                                                  │
│               │                                                              │
│               ▼                                                              │
│    ┌─────────────────────┐                                                  │
│    │    SPIRE Agent      │  Attests workloads via Docker labels             │
│    │  (Workload Attester)│  Provides SVIDs via Unix socket                  │
│    └──────────┬──────────┘                                                  │
│               │                                                              │
│    ┌──────────┴──────────┬──────────────────┬──────────────────┐           │
│    ▼                     ▼                  ▼                  ▼            │
│  ┌────────┐         ┌────────┐         ┌────────┐         ┌────────┐       │
│  │Postgres│         │ Redis  │         │  NATS  │         │ Norns  │       │
│  │  SVID  │◀───────▶│  SVID  │◀───────▶│  SVID  │◀───────▶│  SVID  │       │
│  └────────┘  mTLS   └────────┘  mTLS   └────────┘  mTLS   └────────┘       │
│                                                                              │
│    All inter-service communication is encrypted and authenticated           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Zitadel Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ZITADEL ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    USERS                                      MACHINES                       │
│    ─────                                      ────────                       │
│                                                                              │
│    ┌─────────┐  ┌─────────┐  ┌─────────┐    ┌─────────┐  ┌─────────┐       │
│    │ Browser │  │ Browser │  │ Browser │    │  Norns  │  │   MCP   │       │
│    │ (Admin) │  │  (Dev)  │  │  (User) │    │ (Agent) │  │ (Tools) │       │
│    └────┬────┘  └────┬────┘  └────┬────┘    └────┬────┘  └────┬────┘       │
│         │            │            │              │            │             │
│         └────────────┴────────────┴──────┬───────┴────────────┘             │
│                                          │                                   │
│                                          ▼                                   │
│                               ┌─────────────────────┐                       │
│                               │      ZITADEL        │                       │
│                               │   Identity Provider │                       │
│                               │                     │                       │
│                               │  • OIDC for humans  │                       │
│                               │  • OAuth 2.1 for    │                       │
│                               │    machines         │                       │
│                               │  • Service accounts │                       │
│                               └──────────┬──────────┘                       │
│                                          │                                   │
│         ┌────────────────────────────────┼────────────────────────────────┐ │
│         ▼                                ▼                                ▼ │
│    ┌─────────┐                    ┌─────────────┐                 ┌────────┐│
│    │ Grafana │                    │ Hliðskjálf  │                 │LangFuse││
│    │  (SSO)  │                    │    (SSO)    │                 │ (SSO)  ││
│    └─────────┘                    └─────────────┘                 └────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Runbook Index

### Security Runbooks (Priority)
- [ ] **RUNBOOK-004**: SPIRE Management (Bootstrap, Registration, Rotation)
- [ ] **RUNBOOK-005**: Zitadel Management (Setup, SSO, Service Accounts)
- [ ] **RUNBOOK-006**: OpenBao/Vault (Unseal, Secrets, Rotation)
- [ ] **RUNBOOK-007**: Certificate Management (mkcert, SVID, TLS)

### Infrastructure Runbooks
- [ ] **RUNBOOK-001**: Deploy new Docker service
- [ ] **RUNBOOK-002**: Add new domain to Traefik
- [ ] **RUNBOOK-003**: Generate/update certificates

### Service Runbooks
- [ ] **RUNBOOK-010**: Deploy new agent type
- [ ] **RUNBOOK-011**: Update agent configuration
- [ ] **RUNBOOK-012**: Add MCP server (with OAuth)
- [ ] **RUNBOOK-013**: Create Zitadel service account

### Voice & External Integration
- [x] **RUNBOOK-020**: Add Bifrost messaging adapter
- [x] **RUNBOOK-021**: Add Bifrost AI backend
- [x] **RUNBOOK-022**: Configure voice agent (ravenvoice)

---

## Success Criteria

### Phase 0 (Zero Trust) ✅ COMPLETE:
- [x] SPIRE server healthy
- [x] SPIRE agent healthy
- [x] All workloads registered with SPIFFE IDs
- [x] TLS enabled on NATS, PostgreSQL, Redis
- [x] Platform user standardized (ravenhelm:1001:1001)
- [x] All services running as ravenhelm user
- [x] Volume initialization script created (`scripts/init-platform.sh`)
- [x] RUNBOOK-004 (SPIRE) and RUNBOOK-005 (File Ownership) documented

### Phase 1 (Identity) Complete When:
- [x] Zitadel accessible at zitadel.ravenhelm.test:15443
- [x] Grafana login via Zitadel SSO
- [ ] Hliðskjálf login via Zitadel SSO
- [ ] Norns has service account
- [ ] MCP tools require OAuth tokens

### Phase 2 (Secrets) Complete When: ✅
- [x] LocalStack with persistence enabled
- [x] All secrets migrated to AWS Secrets Manager
- [x] S3 buckets configured (artifacts, backups, logs, terraform, templates)
- [x] Redis AUTH enabled
- [x] PostgreSQL credentials in Secrets Manager
- [x] Python SecretsClient created (`hlidskjalf/src/core/secrets.py`)
- [x] Database backup-to-S3 script created
- [x] Secret rotation documented (RUNBOOK-010)

### Phase 3 (Proxy) Complete When: ✅ COMPLETE
- [x] Traefik replacing nginx
- [x] TLS termination at edge
- [x] Forward auth middleware active (oauth2-proxy + Zitadel)
- [x] All *.ravenhelm.test routes working
- [x] Zero-trust: Internal services require authentication
- [x] Zero-trust: Public services (IdP, auth) accessible without pre-auth

### Phase 4 (Workflow) Complete When:
- [ ] GitLab CE deployed with SSO
- [ ] ravenmaskos template importable
- [ ] New project workflow documented
- [ ] Terraform can deploy to AWS

---

## Service Inventory & Modular Compose Structure

The platform uses a **modular compose structure** for improved stability and development velocity:

```bash
# Quick start scripts
./scripts/start-platform.sh     # Full platform (all stacks)
./scripts/start-dev.sh           # Minimal dev (infra + security + LangGraph)
./scripts/start-observability.sh # Add observability to running stack
```

See [`docs/runbooks/RUNBOOK-030-compose-management.md`](docs/runbooks/RUNBOOK-030-compose-management.md) for stack management.

### Stack Organization

**Infrastructure** (`compose/docker-compose.infrastructure.yml`)
- postgres, redis, nats, localstack, openbao

**Security** (`compose/docker-compose.security.yml`)
- spire-server, spire-agent, postgres-spiffe-helper, redis-spiffe-helper, nats-spiffe-helper, mcp-gitlab-spiffe-helper, zitadel, oauth2-proxy

**Observability** (`compose/docker-compose.observability.yml`)
- prometheus, loki, tempo, alloy, grafana, alertmanager, langfuse, phoenix

**Events** (`compose/docker-compose.events.yml`)
- redpanda, redpanda-console

**AI Infrastructure** (`compose/docker-compose.ai-infra.yml`)
- ollama, hf-reasoning, hf-agents, weaviate, embeddings, reranker, docling, memgraph, neo4j

**LangGraph & Hlidskjalf** (`compose/docker-compose.langgraph.yml`) - **Isolated**
- langgraph (Norns agent), hlidskjalf (API), hlidskjalf-ui

**GitLab** (`compose/docker-compose.gitlab.yml`)
- gitlab, gitlab-runner

**Integrations** (`compose/docker-compose.integrations.yml`)
- mcp-server-gitlab, n8n, livekit

### Service Status

All 40 services are organized into 8 modular stacks. Start/stop independently as needed.

---

## Norns AI Capabilities

### Current Capabilities

| Capability | Status | Implementation |
|------------|--------|----------------|
| Workspace file access | ✅ | `workspace_list`, `workspace_read`, `workspace_write` |
| Terminal commands | ✅ | `execute_terminal_command` |
| Web search | ✅ | `web_search`, `fetch_url` |
| Memory (Huginn/Muninn) | ✅ | State plane + episodic memory |
| Context (Frigg) | ✅ | User persona tracking |
| Domain knowledge (Mímir) | ✅ | Dossier-based ontology |
| Runtime LLM config | ✅ | Session-scoped model switching |
| Skills system | ✅ | Skill discovery, creation, use |

### Planned Enhancements (Phase 6+)

| Capability | Priority | Status | Notes |
|------------|----------|--------|-------|
| Alert handling | 🔴 | ⏳ | Receive alerts, correlate, remediate |
| Docker control | 🔴 | ⏳ | Restart containers, check health |
| Subagent spawning | 🟡 | ⏳ | Deploy specialized agents via UI |
| RAG pipeline | 🟡 | ⏳ | Runbook search via vector embeddings |
| Voice interface | 🟡 | ⏳ | LiveKit integration |
| Cost tracking | 🟡 | ⏳ | Token usage per conversation |

---

## MCP Servers (Model Context Protocol)

MCP servers expose tools and resources that AI agents can use. The Norns agent can call these servers to perform platform operations.

### Current MCP Infrastructure

| Component | Type | Status | Purpose |
|-----------|------|--------|---------|
| Bifrost MCP Backend | Client | ✅ | Consumes MCP servers for AI backends |
| LangGraph Tools | Native | ✅ | File, terminal, web search tools |

### Planned MCP Servers

| Server | Purpose | Tools | Priority |
|--------|---------|-------|----------|
| **gitlab-mcp** | GitLab management | `create_user`, `set_admin`, `add_to_group`, `create_project`, `create_webhook` | 🔴 High |
| **zitadel-mcp** | Identity management | `get_user_roles`, `create_service_account`, `assign_role` | 🔴 High |
| **docker-mcp** | Container management | `list_containers`, `restart_container`, `view_logs`, `check_health` | 🟡 Medium |
| **traefik-mcp** | Routing management | `add_route`, `list_routes`, `check_certificate` | 🟡 Medium |
| **observability-mcp** | Monitoring queries | `query_prometheus`, `search_logs`, `get_traces` | 🟡 Medium |

### MCP Server Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NORNS AGENT (LangGraph)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│    │  Native    │  │  gitlab    │  │  zitadel   │  │  docker    │          │
│    │  Tools     │  │   -mcp     │  │   -mcp     │  │   -mcp     │          │
│    └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘          │
│          │               │               │               │                  │
│          │     MCP Protocol (HTTP/JSON-RPC)              │                  │
│          │               │               │               │                  │
│          ▼               ▼               ▼               ▼                  │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐           │
│    │Workspace │    │ GitLab   │    │ Zitadel  │    │ Docker   │           │
│    │Terminal  │    │   API    │    │   API    │    │ Socket   │           │
│    │Web Search│    │          │    │          │    │          │           │
│    └──────────┘    └──────────┘    └──────────┘    └──────────┘           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation Plan (Phase 4 Task: MCP Shared Services Tool)

**Phases:**
1. **Research** - MCP protocol spec, existing implementations, OAuth integration patterns
2. **Architect** - Unified server design, tool schemas, authentication flow
3. **Build** - Implement tools for GitLab, Zitadel, Docker
4. **Test** - Unit tests, integration tests, MCP compliance
5. **UAT** - Norns agent exercises all tools in real scenarios

**Deliverables:**
1. **GitLab MCP Tools** (First Priority)
   - `gitlab.users.list` - List users
   - `gitlab.users.set_admin` - Promote/demote admin
   - `gitlab.groups.add_member` - Add user to group with role
   - `gitlab.projects.create` - Create new project
   - `gitlab.webhooks.create` - Set up webhooks

2. **Zitadel MCP Tools**
   - `zitadel.users.get_roles` - Query user roles
   - `zitadel.users.assign_role` - Assign role to user
   - `zitadel.service_accounts.create` - Create service account

3. **Docker MCP Tools**
   - `docker.containers.list` - List containers with health
   - `docker.containers.restart` - Restart container
   - `docker.containers.logs` - Get recent logs

---

## Quick Reference

### Trust Domain
```
Trust Domain: ravenhelm.local
SPIRE Server: spire-server:8081
SPIRE Agent Socket: /tmp/spire-agent/public/api.sock
```

### Key Commands
```bash
# Start SPIRE
./spire/init-spire.sh ca
docker compose up -d spire-server spire-agent
./spire/init-spire.sh bootstrap

# Check SPIRE health
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server healthcheck
docker exec gitlab-sre-spire-agent /opt/spire/bin/spire-agent healthcheck

# List registered workloads
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry show
```

---

*"Security is not a feature. It's the foundation."*

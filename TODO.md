# Hliðskjálf Platform TODO

> **Security First — Build on a solid foundation**

---

## 🔴 Critical - Phase 0: Zero Trust (SPIRE)

**Every service gets identity. Every connection is encrypted.**

### SPIRE Bootstrap
- [ ] Generate upstream CA: `./spire/init-spire.sh ca`
- [ ] Start SPIRE server: `docker compose up -d spire-server`
- [ ] Start SPIRE agent: `docker compose up -d spire-agent`
- [ ] Bootstrap workloads: `./spire/init-spire.sh bootstrap`
- [ ] Verify: `docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry show`

### mTLS Enablement
- [ ] Enable mTLS on NATS
- [ ] Enable mTLS on PostgreSQL
- [ ] Enable mTLS on Redis
- [ ] Enable mTLS on Redpanda
- [ ] Update Hliðskjálf to use SVID
- [ ] Update Norns/LangGraph to use SVID

### Documentation
- [x] **RUNBOOK-004**: SPIRE Management (Bootstrap, Registration, Rotation)

---

## 🔴 Critical - Phase 1: Identity (Zitadel)

**All UIs behind SSO. All machines use OAuth.**

### Zitadel Deployment
- [ ] Add Zitadel to docker-compose.yml
- [ ] Configure PostgreSQL database for Zitadel
- [ ] Bootstrap Zitadel admin user
- [ ] Create "Ravenhelm" project
- [ ] Configure OIDC applications

### SSO Integration
- [ ] Configure Grafana OIDC
- [ ] Configure Hliðskjálf OIDC
- [ ] Configure LangFuse OIDC
- [ ] Configure Redpanda Console OIDC

### Machine Auth
- [ ] Create Norns service account
- [ ] Configure MCP OAuth 2.1 middleware
- [ ] Issue JWT tokens for agent APIs

### Documentation
- [ ] **RUNBOOK-005**: Zitadel Management

---

## 🔴 Critical - Phase 2: Secrets (OpenBao)

**No secrets in .env files. Everything in Vault.**

### OpenBao Setup
- [ ] Unseal OpenBao
- [ ] Configure auto-unseal (optional)
- [ ] Create secrets engines (kv, database, pki)

### Secret Migration
- [ ] Move all .env secrets to OpenBao
- [ ] Configure dynamic database credentials
- [ ] Configure Terraform to read from Vault
- [ ] Remove plaintext secrets from repo

### Documentation
- [ ] **RUNBOOK-006**: OpenBao Management

---

## 🟡 High Priority - Phase 3: Proxy (Traefik)

**TLS termination at edge. Auth middleware.**

### Traefik Deployment
- [ ] Deploy Traefik with Docker labels
- [ ] Configure TLS termination
- [ ] Add Zitadel forward auth middleware
- [ ] Migrate all routes from nginx

### Validation
- [ ] Test all `*.ravenhelm.test` endpoints
- [ ] Verify auth required for all UIs
- [ ] Verify mTLS to backend services

---

## 🟡 High Priority - Phase 4: Core Workflow

**Secure project creation and deployment**

### GitLab
- [ ] Deploy GitLab CE with SSO
- [ ] Import ravenmaskos template
- [ ] Configure GitLab Runner

### AWS Integration
- [ ] Store AWS credentials in OpenBao
- [ ] Configure Terraform to use Vault
- [ ] Test deployment to staging

---

## 🟢 Medium - Phase 5: Advanced Features

### Voice & External
- [ ] LiveKit with mTLS
- [ ] Bifrost with OAuth
- [ ] ravenvoice integration

### Observability
- [ ] Cost tracking dashboards
- [ ] Audit log aggregation
- [ ] Security alerts

---

## ✅ Completed

### Infrastructure
- [x] Shared services running (Postgres, Redis, NATS, Redpanda, Ollama)
- [x] SPIRE configured in docker-compose
- [x] Port registry created
- [x] Observability stack deployed

### Security Foundation
- [x] SPIRE server/agent configs written
- [x] init-spire.sh bootstrap script
- [x] Docker labels for workload attestation

### AI/Norns
- [x] LangGraph server running
- [x] Norns agent operational
- [x] Cognitive memory (Huginn, Muninn, Mímir)

### Libraries
- [x] ravenvoice (voice agent library)
- [x] Bifrost gateway (external chat)

### Runbooks
- [x] RUNBOOK-004: SPIRE Management
- [x] RUNBOOK-020: Bifrost Adapter
- [x] RUNBOOK-021: Bifrost AI Backend
- [x] RUNBOOK-022: Voice Agent

---

## Quick Reference

### Security First Commands

```bash
# Phase 0: SPIRE
./spire/init-spire.sh ca
docker compose up -d spire-server spire-agent
./spire/init-spire.sh bootstrap

# Verify SPIRE
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server healthcheck
docker exec gitlab-sre-spire-agent /opt/spire/bin/spire-agent healthcheck

# List workloads
docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry show
```

### Files

| File | Purpose |
|------|---------|
| `spire/server/server.conf` | SPIRE server config |
| `spire/agent/agent.conf` | SPIRE agent config |
| `spire/init-spire.sh` | Bootstrap script |
| `config/port_registry.yaml` | Port assignments |

---

*"Security is not a feature. It's the foundation."*

*See `PROJECT_PLAN.md` for full roadmap*

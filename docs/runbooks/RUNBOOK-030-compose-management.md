# RUNBOOK-030: Compose Management

## Purpose

Manage the modular Docker Compose stack structure for improved stability, resource isolation, and development velocity.

---

## Architecture Overview

The platform is split into 8 independent compose stacks:

```
compose/
├── docker-compose.base.yml            # Shared networks & volumes
├── docker-compose.infrastructure.yml  # postgres, redis, nats, localstack, openbao
├── docker-compose.security.yml        # SPIRE, Zitadel, oauth2-proxy, spiffe-helpers
├── docker-compose.observability.yml   # Grafana, Prometheus, Loki, Tempo, LangFuse, Phoenix
├── docker-compose.events.yml          # Redpanda, Redpanda Console
├── docker-compose.ai-infra.yml        # Ollama, HF models, Weaviate, embeddings, graphs
├── docker-compose.langgraph.yml       # LangGraph (Norns), Hlidskjalf API & UI
├── docker-compose.gitlab.yml          # GitLab CE, GitLab Runner
└── docker-compose.integrations.yml    # MCP server, n8n, LiveKit
```

### Dependency Order

1. **Infrastructure** - Foundational services (no dependencies)
2. **Security** - SPIRE & Zitadel (depends on: infrastructure for postgres)
3. **AI Infrastructure** - LLMs and vector DBs (independent)
4. **Observability** - Metrics, logs, traces (independent)
5. **Events** - Redpanda streaming (independent)
6. **LangGraph** - Control plane (depends on: infrastructure, security for Zitadel)
7. **GitLab** - Source control (depends on: security for Zitadel)
8. **Integrations** - MCP, n8n, LiveKit (depends on: infrastructure, gitlab)

---

## Quick Start Scripts

### Start Full Platform

```bash
./scripts/start-platform.sh
```

Starts all 8 stacks in dependency order.

### Start Dev Mode (Minimal)

```bash
./scripts/start-dev.sh
```

Starts only:
- Infrastructure (postgres, redis, nats, localstack, openbao)
- Security (SPIRE, Zitadel)
- AI Infrastructure (Ollama only)
- LangGraph & Hlidskjalf

### Add Observability

```bash
./scripts/start-observability.sh
```

Adds Grafana stack to running platform.

---

## Manual Stack Management

### Start Individual Stacks

```bash
# Infrastructure first
docker compose -f compose/docker-compose.infrastructure.yml up -d

# Security (after infrastructure)
docker compose -f compose/docker-compose.security.yml up -d

# Control plane (after infrastructure + security)
docker compose -f compose/docker-compose.langgraph.yml up -d

# Observability (independent)
docker compose -f compose/docker-compose.observability.yml up -d
```

### Stop Individual Stacks

```bash
# Stop only observability
docker compose -f compose/docker-compose.observability.yml down

# Stop LangGraph/Hlidskjalf (leaves infrastructure running)
docker compose -f compose/docker-compose.langgraph.yml down
```

### Restart Specific Services

```bash
# Restart just LangGraph (Norns agent)
docker compose -f compose/docker-compose.langgraph.yml restart langgraph

# Restart Hlidskjalf UI only
docker compose -f compose/docker-compose.langgraph.yml restart hlidskjalf-ui
```

### View Logs

```bash
# All services in a stack
docker compose -f compose/docker-compose.langgraph.yml logs -f

# Specific service
docker compose -f compose/docker-compose.langgraph.yml logs -f langgraph
```

---

## Common Workflows

### Rebuild LangGraph After Code Changes

```bash
# Stop, rebuild, and restart
docker compose -f compose/docker-compose.langgraph.yml down
docker compose -f compose/docker-compose.langgraph.yml build
docker compose -f compose/docker-compose.langgraph.yml up -d
```

### Reset All Data

```bash
# WARNING: This removes ALL volumes and data
docker compose -f compose/docker-compose.infrastructure.yml down -v
docker compose -f compose/docker-compose.security.yml down -v
docker compose -f compose/docker-compose.observability.yml down -v
docker compose -f compose/docker-compose.events.yml down -v
docker compose -f compose/docker-compose.ai-infra.yml down -v
docker compose -f compose/docker-compose.langgraph.yml down -v
docker compose -f compose/docker-compose.gitlab.yml down -v
docker compose -f compose/docker-compose.integrations.yml down -v
```

### Test Infrastructure Only

```bash
docker compose -f compose/docker-compose.infrastructure.yml up -d
docker compose -f compose/docker-compose.infrastructure.yml ps
```

---

## Combining Stacks

You can combine multiple compose files:

```bash
# Start infrastructure + security + LangGraph in one command
docker compose \
  -f compose/docker-compose.infrastructure.yml \
  -f compose/docker-compose.security.yml \
  -f compose/docker-compose.langgraph.yml \
  up -d
```

---

## Troubleshooting

### Services Won't Start

**Check dependency order:**
- Infrastructure must be healthy before LangGraph
- Security must be running before Zitadel-dependent services

```bash
# Check health of dependencies
docker compose -f compose/docker-compose.infrastructure.yml ps
docker compose -f compose/docker-compose.security.yml ps
```

### Port Conflicts

Each stack uses different ports. If you see port conflicts:

```bash
# Check what's using the port
lsof -i :5432  # Example for postgres
```

### Network Issues

Ensure `platform_net` exists:

```bash
./scripts/create_traefik_networks.sh
```

### Service Dependencies

If a service can't reach another:

1. Both must be on `platform_net`
2. Check service names match (e.g., `postgres` not `gitlab-sre-postgres`)
3. Verify the dependency stack is running

---

## Benefits of Modular Structure

### Minimize Restarts

Updating Grafana config only restarts observability stack:

```bash
# Edit observability/grafana/...
docker compose -f compose/docker-compose.observability.yml restart grafana
# GitLab, LangGraph, infrastructure keep running
```

### Resource Control

You can allocate resources per stack in the future:

```bash
# Deploy only what you need in dev
docker compose -f compose/docker-compose.infrastructure.yml up -d
docker compose -f compose/docker-compose.langgraph.yml up -d
# Saves ~8GB RAM by not starting GitLab, observability, etc.
```

### Independent Development

- Work on LangGraph without full platform
- Test infrastructure changes in isolation
- Add observability when debugging

---

## Profiles

AI Infrastructure stack supports profiles:

```bash
# Start with RAG pipeline (Weaviate, embeddings, etc.)
docker compose -f compose/docker-compose.ai-infra.yml --profile docling up -d

# Start with HuggingFace models
docker compose -f compose/docker-compose.ai-infra.yml --profile huggingface up -d
```

---

## Migrating From Monolithic docker-compose.yml

The root `docker-compose.yml` remains as reference. To switch:

1. **Stop old stack**: `docker compose down` (in root)
2. **Use new scripts**: `./scripts/start-dev.sh` or `./scripts/start-platform.sh`
3. **No data loss**: All volumes are preserved

---

## References

- [`compose/docker-compose.base.yml`](../../compose/docker-compose.base.yml) - Shared definitions
- [`scripts/start-platform.sh`](../../scripts/start-platform.sh) - Full platform startup
- [`scripts/start-dev.sh`](../../scripts/start-dev.sh) - Minimal dev startup
- [`config/port_registry.yaml`](../../config/port_registry.yaml) - Port allocations

---

## Change Log

| Date | Change |
|------|--------|
| 2025-12-04 | Initial modular structure created |


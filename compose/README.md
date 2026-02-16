# Ravenhelm Platform - Modular Compose Structure

This directory contains the modular Docker Compose stack for the Ravenhelm platform, split into 8 independent stacks for improved stability, resource isolation, and development velocity.

## Stack Files

| File | Services | Purpose |
|------|----------|---------|
| [`docker-compose.base.yml`](docker-compose.base.yml) | - | Shared networks & volumes |
| [`docker-compose.infrastructure.yml`](docker-compose.infrastructure.yml) | postgres, redis, nats, localstack, openbao | Core data/cache/messaging |
| [`docker-compose.security.yml`](docker-compose.security.yml) | SPIRE, Zitadel, oauth2-proxy, spiffe-helpers | Zero-trust identity & SSO |
| [`docker-compose.observability.yml`](docker-compose.observability.yml) | Grafana, Prometheus, Loki, Tempo, LangFuse, Phoenix | Metrics, logs, traces |
| [`docker-compose.events.yml`](docker-compose.events.yml) | redpanda, redpanda-console | Kafka-compatible streaming |
| [`docker-compose.ai-infra.yml`](docker-compose.ai-infra.yml) | ollama, HF models, Weaviate, embeddings, graphs | LLMs & vector DBs |
| [`docker-compose.langgraph.yml`](docker-compose.langgraph.yml) | langgraph, hlidskjalf, hlidskjalf-ui | **Norns agent + Platform dashboard (isolated)** |
| [`docker-compose.gitlab.yml`](docker-compose.gitlab.yml) | gitlab, gitlab-runner | Source control & CI/CD |
| [`docker-compose.integrations.yml`](docker-compose.integrations.yml) | mcp-server-gitlab, n8n, livekit | MCP tools, workflows, voice |

## Quick Start

### Full Platform
```bash
cd /Users/nwalker/Development/hlidskjalf
./scripts/start-platform.sh
```

### Minimal Dev (Fast Inner Loop)
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

## Individual Stack Management

### Start a Stack
```bash
docker compose -f compose/docker-compose.langgraph.yml up -d
```

### Stop a Stack
```bash
docker compose -f compose/docker-compose.langgraph.yml down
```

### Restart a Service
```bash
docker compose -f compose/docker-compose.langgraph.yml restart langgraph
```

### View Logs
```bash
docker compose -f compose/docker-compose.langgraph.yml logs -f langgraph
```

## Dependency Order

1. **Infrastructure** (no dependencies)
2. **Security** (needs: postgres from infrastructure)
3. **AI Infrastructure** (independent)
4. **Observability** (independent)
5. **Events** (independent)
6. **LangGraph** (needs: infrastructure, security)
7. **GitLab** (needs: security for Zitadel)
8. **Integrations** (needs: infrastructure, gitlab)

## Benefits

### Minimize Restarts
- Updating Grafana config only restarts observability stack
- GitLab, LangGraph, and infrastructure keep running

### Resource Control
- Start only what you need (3 services vs 40)
- Saves ~8GB RAM in dev mode

### Independent Development
- Work on LangGraph without full platform
- Test infrastructure changes in isolation
- Add observability when debugging

### Network Isolation
- Each stack can have dedicated networks (future)
- Better security boundaries

## Backwards Compatibility

The root `docker-compose-modular.yml` includes all stacks:

```bash
docker compose -f docker-compose-modular.yml up -d
```

This provides the same behavior as the original monolithic `docker-compose.yml`.

## Documentation

See [`docs/runbooks/RUNBOOK-030-compose-management.md`](../docs/runbooks/RUNBOOK-030-compose-management.md) for:
- Detailed stack management procedures
- Troubleshooting guide
- Common workflows
- Profile usage (docling, huggingface)

## Migration Notes

- Original `docker-compose.yml` preserved as reference
- All volumes are shared - no data migration needed
- Service names unchanged - existing connections work
- Network `platform_net` remains the shared fabric


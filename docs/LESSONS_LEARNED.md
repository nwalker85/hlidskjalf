# Lessons Learned

This document captures operational insights, architectural decisions, and problem-solving patterns discovered during platform development.

---

## 1. Docker Compose Modularization (2025-12-04)

### Problem
Monolithic `docker-compose.yml` with 40 services caused:
- Cascading restarts when updating any service
- Slow development iteration (must start entire platform)
- Difficult to isolate issues
- Resource waste (running unnecessary services)

### Solution
Split into 8 modular compose stacks:
1. **Infrastructure** - postgres, redis, nats, localstack, openbao
2. **Security** - SPIRE, Zitadel, oauth2-proxy, spiffe-helpers
3. **Observability** - Grafana, Prometheus, Loki, Tempo, LangFuse, Phoenix
4. **Events** - Redpanda, Redpanda Console
5. **AI Infrastructure** - Ollama, HF models, Weaviate, embeddings, graphs
6. **LangGraph** - Norns agent, Hlidskjalf API & UI (isolated per user request)
7. **GitLab** - GitLab CE, GitLab Runner
8. **Integrations** - MCP server, n8n, LiveKit

### Key Insights
- **Isolation is stability**: LangGraph can restart without affecting infrastructure
- **Shared network works**: All stacks use `platform_net` - no network isolation needed yet
- **Convenience matters**: Quick-start scripts (`start-dev.sh`, `start-platform.sh`) improve UX
- **Backwards compatibility**: Wrapper file (`docker-compose-modular.yml`) preserves old behavior
- **Documentation critical**: RUNBOOK-030 ensures operators understand the new structure

### Implementation Details
- Used Docker Compose `include:` directive for shared definitions
- All volumes remain in `docker-compose.base.yml` for centralized management
- Scripts handle dependency order automatically
- Each stack validated with `docker compose config`

### Metrics
- **Dev startup time**: 40 services → 8 services (80% reduction)
- **Memory savings**: ~8GB in dev mode
- **Restart isolation**: Updating Grafana no longer restarts GitLab/LangGraph
- **Files created**: 8 compose files, 3 scripts, 1 runbook, 1 README

---

## Future Lessons

Add new sections here as operational patterns emerge.

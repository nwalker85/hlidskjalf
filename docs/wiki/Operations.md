# Operations

- **Runbooks:** See [Runbook Catalog](Runbook_Catalog.md) for categorized procedures.
- **Checklists:** Use `docs/runbooks/RUNBOOK-001` through `RUNBOOK-022` before promoting changes.
- **Observability:** Follow `docs/runbooks/RUNBOOK-007-observability-setup.md` to keep Grafana dashboards + alerting aligned with deployments.
- **Runbook Maintenance:** Quarterly validate each runbook in a clean environment and capture lessons learned in `docs/LESSONS_LEARNED.md`.
- **Automation Backlog:** Implement the runbook catalog sync pipeline + skills catalog job (see Operations Board).

## Automation Helpers
- `./scripts/sync_wiki.sh` — pushes `docs/wiki/*` into the GitLab wiki (requires `GITLAB_TOKEN`).
- `./scripts/ops_board.py` — list/create/move issues on the Operations Board without leaving the terminal.

Set `GITLAB_TOKEN` before running either script so they can authenticate against `gitlab.ravenhelm.test`.

## Modular Compose Stack Structure

The platform is now split into 8 independent compose stacks for improved stability and development velocity:

- **Infrastructure** (`compose/docker-compose.infrastructure.yml`) - Postgres, Redis, NATS, LocalStack, OpenBao
- **Security** (`compose/docker-compose.security.yml`) - SPIRE, Zitadel, OAuth2-Proxy, SPIFFE helpers
- **Observability** (`compose/docker-compose.observability.yml`) - Grafana, Prometheus, Loki, Tempo, LangFuse, Phoenix
- **Events** (`compose/docker-compose.events.yml`) - Redpanda, Redpanda Console
- **AI Infrastructure** (`compose/docker-compose.ai-infra.yml`) - Ollama, HF models, Weaviate, embeddings, graphs
- **LangGraph** (`compose/docker-compose.langgraph.yml`) - Norns agent, Hliðskjálf API & UI
- **GitLab** (`compose/docker-compose.gitlab.yml`) - GitLab CE, GitLab Runner
- **Integrations** (`compose/docker-compose.integrations.yml`) - MCP server, n8n, LiveKit

### Quick Start

```bash
# Full platform
./scripts/start-platform.sh

# Minimal dev (infrastructure + security + LangGraph only)
./scripts/start-dev.sh

# Add observability to running stack
./scripts/start-observability.sh
```

See [`docs/runbooks/RUNBOOK-030-compose-management.md`](../runbooks/RUNBOOK-030-compose-management.md) for detailed stack management procedures.

## Norns Session Tokens
- The `/norns` console no longer reads `apiUrl`, `assistantId`, or `threadId` from query parameters. Instead, `POST /api/norns/session` encrypts those fields (AES‑256‑GCM using `NORNS_SESSION_SECRET` or `NEXTAUTH_SECRET`) and stores the opaque token in an `HttpOnly` cookie.
- Operators can still share access via **Copy Session Link**, which issues a fresh tokenised URL (`/norns?token=...`). The UI immediately redeems the token, drops it into the cookie, and replaces the URL with `/norns` to keep the navigation bar clean.
- Make sure `NORNS_SESSION_SECRET` is set anywhere the UI runs (dev, preview, prod). Without it the API route throws during boot, so default to the same secret we use for NextAuth if needed.
- Thread switches (new runs, history clicks, resume events) update the stored token automatically so refreshing the page keeps you on the same thread without leaking IDs into the browser history.

## Automation Helpers
- `./scripts/sync_wiki.sh` — pushes `docs/wiki/*` into the GitLab wiki (requires `GITLAB_TOKEN`).
- `./scripts/ops_board.py` — list/create/move issues on the Operations Board without leaving the terminal.

Set `GITLAB_TOKEN` before running either script so they can authenticate against `gitlab.ravenhelm.test`.


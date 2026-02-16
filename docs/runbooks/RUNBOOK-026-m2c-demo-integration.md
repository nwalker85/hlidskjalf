# RUNBOOK-026: M2C Demo Integration

This runbook documents how the M2C demo application ports are registered in the shared services port registry and provides the configuration needed to align the project with ravenhelm infrastructure.

---

## 1. Overview

**M2C Demo** is a grid/utility compliance monitoring platform with LangGraph agents. It consists of:

| Component | Purpose | External Port | Internal Port |
|-----------|---------|---------------|---------------|
| Backend | Express + LangGraph API | 8205 | 4000 |
| Visualizer | Next.js dashboard UI | 3205 | 3000 |
| PostgreSQL | Isolated database | 5433 | 5432 |
| n8n | Workflow orchestration | 5679 | 5678 |
| Redpanda | Kafka-compatible streaming | 29092/28081/28082/29644 | 9092/8081/8082 |
| Redpanda Console | Kafka web UI | 8089 | 8080 |

> **Note:** Redpanda uses 29xxx ports (not 19xxx) to avoid conflicts with `gitlab-sre-redpanda` which uses 19xxx.

---

## 2. Port Registry Entries

All ports are registered in `config/port_registry.yaml`:

### Reserved Ports (Infrastructure)

```yaml
# m2c-demo isolated infrastructure
- port: 5433
  service: m2c-demo-postgres
  description: M2C demo PostgreSQL (isolated from shared 5432)
- port: 5679
  service: m2c-demo-n8n
  description: M2C demo n8n instance (isolated from shared 5678)
- port: 29092
  service: m2c-redpanda-kafka-ext
  description: M2C Redpanda external Kafka listener (29xxx avoids gitlab-sre-redpanda)
- port: 28081
  service: m2c-redpanda-schema-ext
  description: M2C Redpanda external Schema Registry
- port: 28082
  service: m2c-redpanda-proxy-ext
  description: M2C Redpanda external HTTP Proxy
- port: 29644
  service: m2c-redpanda-admin
  description: M2C Redpanda Admin API
- port: 8089
  service: m2c-redpanda-console
  description: M2C Redpanda Console UI (8089 avoids gitlab-sre-redpanda-console)
```

### Work Project Entry

```yaml
work:
  m2c-demo:
    api_port: 8205
    ui_port: 3205
    domain: m2c.ravenhelm.test
    domain_aliases:
      - m2c-api.ravenhelm.test
```

---

## 3. Environment Configuration

Create a `.env` file in `/Users/nwalker/Development/Quant/Projects/m2c-demo/` with these registry-aligned values:

```bash
# ============================================================================
# M2C Demo - Environment Configuration
# ============================================================================
# Port assignments aligned with ravenhelm shared services port registry:
# See: /Users/nwalker/Development/hlidskjalf/config/port_registry.yaml (work.m2c-demo)
# ============================================================================

# ── PostgreSQL ───────────────────────────────────────────────────────────────
# Using port 5433 to avoid conflict with shared postgres on 5432
POSTGRES_EXTERNAL_PORT=5433
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=m2c
POSTGRES_PASSWORD=m2c_dev_password
POSTGRES_DB=m2c

# ── Backend API ──────────────────────────────────────────────────────────────
# External port 8205 (work_api range), internal container port 4000
BACKEND_PORT=8205

# ── Visualizer UI ────────────────────────────────────────────────────────────
# External port 3205 (work_ui range), internal container port 3000
VISUALIZER_PORT=3205

# ── n8n Workflow Engine ──────────────────────────────────────────────────────
# Using port 5679 to avoid conflict with shared n8n on 5678
N8N_PORT=5679
N8N_BASIC_AUTH_ACTIVE=false
N8N_HOST=localhost
N8N_PROTOCOL=http
N8N_WEBHOOK_URL=http://localhost:5679/
N8N_TIMEZONE=America/New_York

# ── Redpanda / Kafka ─────────────────────────────────────────────────────────
# External listeners use 29xxx ports to avoid conflict with gitlab-sre-redpanda (19xxx)
# Internal listeners (within m2c-network) use standard ports
KAFKA_UI_PORT=8089

# ── LLM Configuration ────────────────────────────────────────────────────────
# For LangGraph remediation agents
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
REMEDIATION_LLM_PROVIDER=openai
REMEDIATION_LLM_MODEL=gpt-3.5-turbo
REMEDIATION_SKIP_LLM=true

# ── LangGraph Feature Flags ──────────────────────────────────────────────────
USE_LANGGRAPH=true
USE_LANGGRAPH_TOPOLOGY=true
USE_LANGGRAPH_COMPLIANCE=true
```

---

## 4. Networking Alignment with Shared Services

1. Ensure the shared platform network exists: `/Users/nwalker/Development/hlidskjalf/scripts/create_traefik_networks.sh` creates/updates `platform_net` with the canonical CIDR.
2. `/Users/nwalker/Development/Quant/Projects/m2c-demo/docker-compose.yml` now attaches HTTP-facing services (backend, visualizer, n8n, Redpanda, Redpanda Console) to both `m2c-network` and the external `platform_net`. Postgres and the Redpanda init job remain isolated on `m2c-network` only.
3. Because Traefik also lives on `platform_net`, routers defined in `/Users/nwalker/Development/hlidskjalf/ravenhelm-proxy/dynamic.yml` can talk directly to the containers via their hostnames (`m2c-backend`, `m2c-visualizer`, `m2c-n8n`, `m2c-redpanda-console`). Host port mappings remain available for localhost testing but Traefik no longer depends on them.

---

## 5. Docker Compose Updates

Update `docker-compose.yml` port mappings to use environment variables consistently:

### Current (Original)

```yaml
services:
  postgres:
    ports:
      - "${POSTGRES_EXTERNAL_PORT}:5432"  # ✓ Already parameterized
  
  backend:
    ports:
      - "${BACKEND_PORT:-4000}:4000"      # ⚠ Default should be 8205
  
  visualizer:
    ports:
      - "${VISUALIZER_PORT}:3000"         # ✓ Already parameterized
  
  n8n:
    ports:
      - "${N8N_PORT}:5678"                # ✓ Already parameterized
  
  redpanda:
    ports:
      - "19092:19092"                     # ✓ High ports for dual-stack
      - "18081:18081"
      - "18082:18082"
      - "9644:9644"
  
  redpanda-console:
    ports:
      - "${KAFKA_UI_PORT:-8088}:8080"     # ✓ Already parameterized
```

### Recommended Change

Update the backend service default:

```yaml
backend:
  ports:
    - "${BACKEND_PORT:-8205}:4000"  # Changed default from 4000 to 8205
```

---

## 6. Traefik Integration

Traefik routes are **already configured** in `ravenhelm-proxy/dynamic.yml`. The following domains are available:

| Domain | Service | Port |
|--------|---------|------|
| `https://m2c.ravenhelm.test` | Visualizer UI | 3205 |
| `https://m2c-api.ravenhelm.test` | Backend API | 8205 |
| `https://m2c-n8n.ravenhelm.test` | n8n Workflows | 5679 |
| `https://m2c-redpanda.ravenhelm.test` | Redpanda Console | 8089 |

### Enable Traefik Mode

To use HTTPS via Traefik instead of localhost, uncomment these lines in `.env`:

```bash
NEXT_PUBLIC_BACKEND_URL=https://m2c-api.ravenhelm.test
NEXT_PUBLIC_WS_URL=wss://m2c-api.ravenhelm.test/ws
```

Then rebuild the visualizer:

```bash
docker compose up -d --build visualizer
```

---

## 7. Environment Variables (Localhost Audit)

All components use environment variables with sensible localhost fallbacks. The codebase has been audited for hardcoded references:

### Backend (TypeScript)
- `POSTGRES_HOST` - defaults to `localhost` for development
- `KAFKA_BROKERS` - defaults to `localhost:9092`
- No hardcoded URLs in business logic

### Visualizer (Next.js)
All API/WebSocket URLs use environment variables:

```typescript
// Default fallback is localhost:8205 (registry-aligned)
const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8205';
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8205/ws';
```

### docker-compose.yml
Visualizer environment is fully parameterized:

```yaml
visualizer:
  environment:
    - NEXT_PUBLIC_BACKEND_URL=${NEXT_PUBLIC_BACKEND_URL:-http://localhost:${BACKEND_PORT:-8205}}
    - NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL:-ws://localhost:${BACKEND_PORT:-8205}/ws}
```

---

## 8. Validation Checklist

- [ ] `.env` file created with registry-aligned ports
- [ ] `docker compose up -d` succeeds without port conflicts
- [ ] Backend health check passes: `curl http://localhost:8205/health`
- [ ] Visualizer accessible at `http://localhost:3205`
- [ ] n8n accessible at `http://localhost:5679`
- [ ] Redpanda Console accessible at `http://localhost:8089`
- [ ] (If Traefik) `https://m2c.ravenhelm.test` resolves correctly
- [ ] (If Traefik) WebSocket connects via `wss://m2c-api.ravenhelm.test/ws`

---

## 9. Port Conflict Resolution

M2C demo uses unique ports to coexist with the shared platform (`gitlab-sre-*` services):

| Service | Shared Platform Port | M2C Demo Port |
|---------|---------------------|---------------|
| PostgreSQL | 5432 | 5433 |
| n8n | 5678 | 5679 |
| Redpanda Kafka (external) | 19092 | 29092 |
| Redpanda Schema (external) | 18081 | 28081 |
| Redpanda Proxy (external) | 18082 | 28082 |
| Redpanda Admin | 19644 | 29644 |
| Redpanda Console | 8088 | 8089 |

Redpanda uses 29xxx ports instead of 19xxx to avoid conflicts with `gitlab-sre-redpanda`. Both can run simultaneously.

---

## References

- [RUNBOOK-024: Add a New Shared Service](RUNBOOK-024-add-shared-service.md)
- [Port Registry](../../config/port_registry.yaml)
- [M2C Demo Project](/Users/nwalker/Development/Quant/Projects/m2c-demo/)


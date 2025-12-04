#!/usr/bin/env bash
# Ravenhelm Platform - Start Full Platform
# ==========================================
# Starts all platform services in dependency order

set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "$0")/../compose" && pwd)"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT_DIR"

echo "========================================="
echo "Ravenhelm Platform - Full Stack Startup"
echo "========================================="
echo

# Ensure networks exist
echo "→ Creating platform networks..."
./scripts/create_traefik_networks.sh

echo
echo "→ Starting Infrastructure Stack (postgres, redis, nats, localstack, openbao)..."
docker compose --env-file .env -f compose/docker-compose.infrastructure.yml up -d

echo
echo "→ Starting Security Stack (SPIRE, Zitadel, oauth2-proxy)..."
docker compose --env-file .env -f compose/docker-compose.security.yml up -d

echo
echo "→ Waiting for infrastructure to be healthy..."
sleep 10

echo
echo "→ Starting AI Infrastructure (Ollama, vector DB, graphs)..."
docker compose --env-file .env -f compose/docker-compose.ai-infra.yml up -d

echo
echo "→ Starting Observability Stack (Grafana, Prometheus, Loki, Tempo)..."
docker compose --env-file .env -f compose/docker-compose.observability.yml up -d

echo
echo "→ Starting Events Stack (Redpanda)..."
docker compose --env-file .env -f compose/docker-compose.events.yml up -d

echo
echo "→ Starting LangGraph & Hlidskjalf (Control Plane)..."
docker compose --env-file .env -f compose/docker-compose.langgraph.yml up -d

echo
echo "→ Starting GitLab Stack..."
docker compose --env-file .env -f compose/docker-compose.gitlab.yml up -d

echo
echo "→ Starting Integrations (MCP, n8n, LiveKit)..."
docker compose --env-file .env -f compose/docker-compose.integrations.yml up -d

echo
echo "========================================="
echo "✅ Platform Started Successfully!"
echo "========================================="
echo
echo "Key Services:"
echo "  • Hlidskjalf UI:     https://hlidskjalf.ravenhelm.test"
echo "  • Norns (LangGraph): https://norns.ravenhelm.test"
echo "  • GitLab:            https://gitlab.ravenhelm.test"
echo "  • Grafana:           https://grafana.observe.ravenhelm.test"
echo "  • Zitadel:           https://zitadel.ravenhelm.test"
echo
echo "Run 'docker compose ps' to see all services"


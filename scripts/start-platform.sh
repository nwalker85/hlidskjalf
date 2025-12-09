#!/usr/bin/env bash
# Ravenhelm Platform - Start Full Platform
# ==========================================
# Starts all platform services in dependency order

set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "$0")/../compose" && pwd)"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TRAEFIK_COMPOSE="ravenhelm-proxy/docker-compose-traefik.yml"

cd "$ROOT_DIR"

echo "========================================="
echo "Ravenhelm Platform - Full Stack Startup"
echo "========================================="
echo

# Ensure networks exist
echo "→ Creating platform networks..."
./scripts/create_traefik_networks.sh

# Start Traefik first as it's the edge proxy
if [[ -f "$TRAEFIK_COMPOSE" ]]; then
  echo
  echo "→ Starting Traefik (edge proxy)..."
  docker compose -f "$TRAEFIK_COMPOSE" up -d
  echo "✓ Traefik started"
  sleep 3
fi

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
echo "  • Traefik Dashboard: https://proxy.ravenhelm.test"
echo "  • Hlidskjalf UI:     https://hlidskjalf.ravenhelm.test"
echo "  • Norns (LangGraph): https://norns.ravenhelm.test"
echo "  • GitLab:            https://gitlab.ravenhelm.test"
echo "  • Grafana:           https://grafana.observe.ravenhelm.test"
echo "  • Zitadel:           https://zitadel.ravenhelm.test"
echo
echo "External (.dev domains require DNS/port forwarding):"
echo "  • Hlidskjalf UI:     https://hlidskjalf.ravenhelm.dev"
echo "  • Grafana:           https://grafana.ravenhelm.dev"
echo
echo "Run 'docker compose ps' to see all services"
echo "Run 'docker compose -f ravenhelm-proxy/docker-compose-traefik.yml logs -f' to see Traefik logs"


#!/usr/bin/env bash
# Ravenhelm Platform - Start Minimal Dev Stack
# ==============================================
# Starts only essential services for fast inner loop development

set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "$0")/../compose" && pwd)"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT_DIR"

echo "========================================="
echo "Ravenhelm Platform - Dev Mode Startup"
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
echo "→ Starting AI Infrastructure (Ollama only)..."
docker compose --env-file .env -f compose/docker-compose.ai-infra.yml up -d ollama

echo
echo "→ Waiting for core services to be healthy..."
sleep 10

echo
echo "→ Starting LangGraph & Hlidskjalf (Control Plane)..."
docker compose --env-file .env -f compose/docker-compose.langgraph.yml up -d

echo
echo "========================================="
echo "✅ Dev Stack Started!"
echo "========================================="
echo
echo "Running Services (minimal):"
echo "  • Hlidskjalf UI:     https://hlidskjalf.ravenhelm.test"
echo "  • Norns (LangGraph): https://norns.ravenhelm.test"
echo "  • Zitadel:           https://zitadel.ravenhelm.test"
echo
echo "Infrastructure:"
echo "  • PostgreSQL:        localhost:5432"
echo "  • Redis:             localhost:6379"
echo "  • NATS:              localhost:4222"
echo "  • Ollama:            localhost:11434"
echo
echo "To add observability: ./scripts/start-observability.sh"
echo "To add GitLab:        docker compose -f compose/docker-compose.gitlab.yml up -d"


#!/usr/bin/env bash
# Ravenhelm Platform - Add Observability to Running Stack
# =========================================================
# Starts observability stack (Grafana, Prometheus, Loki, Tempo)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT_DIR"

echo "========================================="
echo "Starting Observability Stack"
echo "========================================="
echo

echo "→ Starting Grafana, Prometheus, Loki, Tempo, Alertmanager, LangFuse, Phoenix..."
docker compose --env-file .env -f compose/docker-compose.observability.yml up -d

echo
echo "✅ Observability Stack Started!"
echo
echo "Services:"
echo "  • Grafana:      https://grafana.observe.ravenhelm.test"
echo "  • Prometheus:   http://localhost:9090"
echo "  • Loki:         http://localhost:3100"
echo "  • Tempo:        http://localhost:3200"
echo "  • LangFuse:     https://langfuse.observe.ravenhelm.test"
echo "  • Phoenix:      http://localhost:6006"


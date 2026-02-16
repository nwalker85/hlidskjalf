#!/usr/bin/env bash
# Ravenhelm Platform - Cleanup and Rebuild
# ==========================================
# Stops, cleans up, and optionally rebuilds the entire platform
#
# Usage:
#   ./scripts/cleanup-rebuild-platform.sh [OPTIONS]
#
# Options:
#   --light         Stop containers only (default)
#   --medium        Stop and remove containers, keep volumes (safe)
#   --rebuild       Rebuild images after cleanup
#   --restart       Restart platform after cleanup/rebuild
#
# Examples:
#   ./scripts/cleanup-rebuild-platform.sh --light --restart
#   ./scripts/cleanup-rebuild-platform.sh --medium --rebuild --restart
#
# Note: Volume cleanup (databases, etc.) requires a separate explicit operation.
#       See docs/CLEANUP_REBUILD_GUIDE.md for manual volume management.

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

COMPOSE_DIR="$(cd "$(dirname "$0")/../compose" && pwd)"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT_DIR"

# Parse arguments
CLEANUP_LEVEL="light"
DO_REBUILD=false
DO_RESTART=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --light)
      CLEANUP_LEVEL="light"
      shift
      ;;
    --medium)
      CLEANUP_LEVEL="medium"
      shift
      ;;
    --rebuild)
      DO_REBUILD=true
      shift
      ;;
    --restart)
      DO_RESTART=true
      shift
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Usage: $0 [--light|--medium] [--rebuild] [--restart]"
      exit 1
      ;;
  esac
done

echo "========================================="
echo "Ravenhelm Platform - Cleanup & Rebuild"
echo "========================================="
echo
echo -e "Cleanup Level: ${YELLOW}${CLEANUP_LEVEL}${NC}"
echo -e "Rebuild Images: ${YELLOW}${DO_REBUILD}${NC}"
echo -e "Restart After: ${YELLOW}${DO_RESTART}${NC}"
echo

# ==========================================
# STEP 1: Stop All Services
# ==========================================

echo
echo "========================================="
echo "STEP 1: Stopping All Services"
echo "========================================="
echo

# Stop in reverse order of startup
COMPOSE_FILES=(
  "compose/docker-compose.integrations.yml"
  "compose/docker-compose.gitlab.yml"
  "compose/docker-compose.langgraph.yml"
  "compose/docker-compose.events.yml"
  "compose/docker-compose.observability.yml"
  "compose/docker-compose.ai-infra.yml"
  "compose/docker-compose.security.yml"
  "compose/docker-compose.infrastructure.yml"
)

# Traefik runs in a separate compose file
TRAEFIK_COMPOSE="ravenhelm-proxy/docker-compose-traefik.yml"

for compose_file in "${COMPOSE_FILES[@]}"; do
  if [[ -f "$compose_file" ]]; then
    echo -e "${BLUE}→ Stopping $(basename $compose_file)...${NC}"
    docker compose --env-file .env -f "$compose_file" down --remove-orphans 2>/dev/null || true
  fi
done

# Also stop main docker-compose.yml if it exists
if [[ -f "docker-compose.yml" ]]; then
  echo -e "${BLUE}→ Stopping docker-compose.yml...${NC}"
  docker compose --env-file .env down --remove-orphans 2>/dev/null || true
fi

# Stop Traefik (runs in separate compose file outside of main orchestration)
if [[ -f "$TRAEFIK_COMPOSE" ]]; then
  echo -e "${BLUE}→ Stopping Traefik (ravenhelm-proxy)...${NC}"
  docker compose -f "$TRAEFIK_COMPOSE" down --remove-orphans 2>/dev/null || true
fi

echo -e "${GREEN}✓ All services stopped (including Traefik)${NC}"

# ==========================================
# STEP 2: Cleanup (Based on Level)
# ==========================================

if [[ "$CLEANUP_LEVEL" == "medium" ]]; then
  echo
  echo "========================================="
  echo "STEP 2: Cleanup Resources"
  echo "========================================="
  echo

  echo -e "${BLUE}→ Removing stopped containers...${NC}"
  docker container prune -f 2>/dev/null || true
  echo -e "${GREEN}✓ Containers removed${NC}"

  echo
  echo -e "${BLUE}→ Removing unused networks...${NC}"
  docker network prune -f 2>/dev/null || true
  echo -e "${GREEN}✓ Networks cleaned${NC}"

  echo
  echo -e "${BLUE}→ Removing dangling images...${NC}"
  docker image prune -f 2>/dev/null || true
  echo -e "${GREEN}✓ Dangling images removed${NC}"
fi

# ==========================================
# STEP 3: Rebuild Images (Optional)
# ==========================================

if [[ "$DO_REBUILD" == "true" ]]; then
  echo
  echo "========================================="
  echo "STEP 3: Rebuilding Platform Images"
  echo "========================================="
  echo

  echo -e "${BLUE}→ Building hlidskjalf-api...${NC}"
  docker compose --env-file .env build --no-cache hlidskjalf 2>&1 | grep -E "^#|Building|built|Successfully" || true
  echo -e "${GREEN}✓ hlidskjalf-api built${NC}"

  echo
  echo -e "${BLUE}→ Building hlidskjalf-ui...${NC}"
  docker compose --env-file .env build --no-cache hlidskjalf-ui 2>&1 | grep -E "^#|Building|built|Successfully" || true
  echo -e "${GREEN}✓ hlidskjalf-ui built${NC}"

  echo
  echo -e "${BLUE}→ Building langgraph (Norns)...${NC}"
  docker compose --env-file .env build --no-cache langgraph 2>&1 | grep -E "^#|Building|built|Successfully" || true
  echo -e "${GREEN}✓ langgraph built${NC}"

  echo
  echo -e "${BLUE}→ Building other services...${NC}"
  for compose_file in "${COMPOSE_FILES[@]}"; do
    if [[ -f "$compose_file" ]]; then
      docker compose --env-file .env -f "$compose_file" build --no-cache 2>&1 | grep -E "^#|Building|built|Successfully" || true
    fi
  done
  echo -e "${GREEN}✓ All images rebuilt${NC}"
fi

# ==========================================
# STEP 4: Restart Platform (Optional)
# ==========================================

if [[ "$DO_RESTART" == "true" ]]; then
  echo
  echo "========================================="
  echo "STEP 4: Restarting Platform"
  echo "========================================="
  echo

  # Always start Traefik first as it's the edge proxy
  if [[ -f "$TRAEFIK_COMPOSE" ]]; then
    echo -e "${BLUE}→ Starting Traefik (ravenhelm-proxy)...${NC}"
    # Ensure networks exist first
    ./scripts/create_traefik_networks.sh 2>/dev/null || true
    docker compose -f "$TRAEFIK_COMPOSE" up -d
    echo -e "${GREEN}✓ Traefik started${NC}"
    sleep 3
  fi

  if [[ -x "./scripts/start-platform.sh" ]]; then
    echo -e "${BLUE}→ Running start-platform.sh...${NC}"
    ./scripts/start-platform.sh
  else
    echo -e "${YELLOW}⚠️  start-platform.sh not found or not executable${NC}"
    echo -e "${YELLOW}   Starting services manually...${NC}"
    
    # Ensure networks exist
    echo -e "${BLUE}→ Creating platform networks...${NC}"
    ./scripts/create_traefik_networks.sh 2>/dev/null || true

    # Start in dependency order
    for compose_file in $(echo "${COMPOSE_FILES[@]}" | tr ' ' '\n' | tac | tr '\n' ' '); do
      if [[ -f "$compose_file" ]]; then
        echo -e "${BLUE}→ Starting $(basename $compose_file)...${NC}"
        docker compose --env-file .env -f "$compose_file" up -d
      fi
    done

    if [[ -f "docker-compose.yml" ]]; then
      echo -e "${BLUE}→ Starting docker-compose.yml...${NC}"
      docker compose --env-file .env up -d
    fi

    echo -e "${GREEN}✓ Platform started${NC}"
  fi
fi

# ==========================================
# Summary
# ==========================================

echo
echo "========================================="
echo "✅ Cleanup Complete!"
echo "========================================="
echo
echo "Summary:"
echo -e "  • Cleanup Level: ${YELLOW}${CLEANUP_LEVEL}${NC}"
echo -e "  • Images Rebuilt: ${YELLOW}${DO_REBUILD}${NC}"
echo -e "  • Platform Restarted: ${YELLOW}${DO_RESTART}${NC}"
echo

if [[ "$DO_RESTART" == "true" ]]; then
  echo "Platform is now running. Check status with:"
  echo "  docker compose ps"
  echo
  echo "Key Services:"
  echo "  • Hlidskjalf UI:     https://hlidskjalf.ravenhelm.test"
  echo "  • Hlidskjalf API:    https://hlidskjalf-api.ravenhelm.test"
  echo "  • Norns (LangGraph): https://norns.ravenhelm.test"
  echo "  • GitLab:            https://gitlab.ravenhelm.test"
  echo "  • Grafana:           https://grafana.observe.ravenhelm.test"
  echo "  • Zitadel:           https://zitadel.ravenhelm.test"
else
  echo "Platform is stopped. To start it, run:"
  echo "  ./scripts/start-platform.sh"
  echo
  echo "Or re-run this script with:"
  echo "  ./scripts/cleanup-rebuild-platform.sh --${CLEANUP_LEVEL} --restart"
fi

echo
echo "Done! 🎉"
echo


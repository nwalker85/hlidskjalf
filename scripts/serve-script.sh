#!/bin/bash
# =============================================================================
# Serve Setup Script via HTTP
# =============================================================================
# Simple HTTP server to transfer the setup script to external machine
# without needing SSH.
#
# Usage:
#   ./scripts/serve-script.sh
#
# Then on external machine:
#   curl http://YOUR_IP:8888/setup-model-server-macos.sh -o setup.sh
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8888}"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}       Setup Script HTTP Server                               ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Get local IP addresses
echo -e "${YELLOW}Your IP addresses:${NC}"
ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print "  " $2}'
echo ""

echo -e "${YELLOW}Starting HTTP server on port ${PORT}...${NC}"
echo ""
echo -e "${GREEN}On the external machine (192.168.50.26), run:${NC}"
echo ""
echo -e "  ${BLUE}curl http://YOUR_IP:${PORT}/setup-model-server-macos.sh -o setup.sh${NC}"
echo -e "  ${BLUE}chmod +x setup.sh${NC}"
echo -e "  ${BLUE}./setup.sh${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

cd "$SCRIPT_DIR"
python3 -m http.server "$PORT"


#!/bin/bash
# =============================================================================
# Register External Model Server with SPIRE
# =============================================================================
# This script registers the external model server (models.ravenhelm / 192.168.50.26)
# with the SPIRE server for zero-trust mTLS authentication.
#
# Usage:
#   ./scripts/register-model-server-spire.sh [--generate-token]
#
# Options:
#   --generate-token    Generate and display join token for external agent
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

GENERATE_TOKEN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --generate-token)
            GENERATE_TOKEN=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        External Model Server SPIRE Registration              ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check SPIRE server is running
echo -e "${YELLOW}Checking SPIRE server health...${NC}"
if ! docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server healthcheck &>/dev/null; then
    echo -e "${RED}✗ SPIRE server is not healthy or not running${NC}"
    echo -e "${YELLOW}  Try: docker compose up -d spire-server${NC}"
    exit 1
fi
echo -e "${GREEN}✓ SPIRE server is healthy${NC}"
echo ""

# Register the external agent (if token generation requested)
if [ "$GENERATE_TOKEN" = true ]; then
    echo -e "${YELLOW}Generating join token for external agent...${NC}"
    
    # Create agent entry
    docker exec gitlab-sre-spire-server \
        /opt/spire/bin/spire-server entry create \
        -spiffeID spiffe://ravenhelm.local/agent/model-server \
        -parentID spiffe://ravenhelm.local/spire/server \
        -selector "true" \
        -ttl 3600 \
        -node 2>/dev/null || true
    
    # Generate join token
    JOIN_TOKEN=$(docker exec gitlab-sre-spire-server \
        /opt/spire/bin/spire-server token generate \
        -spiffeID spiffe://ravenhelm.local/agent/model-server \
        -ttl 600 2>/dev/null | grep "Token:" | awk '{print $2}')
    
    if [ -z "$JOIN_TOKEN" ]; then
        echo -e "${RED}✗ Failed to generate join token${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Join token generated${NC}"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}Join Token (expires in 10 minutes):${NC}"
    echo -e "${GREEN}${JOIN_TOKEN}${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${YELLOW}On the external machine (192.168.50.26), run:${NC}"
    echo -e "  sudo /usr/local/bin/spire-agent run \\"
    echo -e "    -config /opt/spire/conf/agent.conf \\"
    echo -e "    -joinToken \"${GREEN}${JOIN_TOKEN}${NC}\""
    echo ""
fi

# Register the model server workload
echo -e "${YELLOW}Registering model server workload...${NC}"

# Check if already registered
if docker exec gitlab-sre-spire-server \
    /opt/spire/bin/spire-server entry show \
    -spiffeID spiffe://ravenhelm.local/workload/model-server 2>/dev/null | grep -q "spiffe://ravenhelm.local/workload/model-server"; then
    echo -e "${YELLOW}⚠ Workload already registered, deleting old entry...${NC}"
    
    ENTRY_ID=$(docker exec gitlab-sre-spire-server \
        /opt/spire/bin/spire-server entry show \
        -spiffeID spiffe://ravenhelm.local/workload/model-server 2>/dev/null | \
        grep "Entry ID" | awk '{print $4}')
    
    docker exec gitlab-sre-spire-server \
        /opt/spire/bin/spire-server entry delete \
        -entryID "$ENTRY_ID" 2>/dev/null || true
fi

# Create new workload entry
# Using unix:uid selector - adjust based on how the model service runs on the external machine
docker exec gitlab-sre-spire-server \
    /opt/spire/bin/spire-server entry create \
    -spiffeID spiffe://ravenhelm.local/workload/model-server \
    -parentID spiffe://ravenhelm.local/agent/model-server \
    -selector unix:uid:1001 \
    -ttl 3600 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Model server workload registered${NC}"
else
    echo -e "${RED}✗ Failed to register workload${NC}"
    exit 1
fi

echo ""

# Verify registration
echo -e "${YELLOW}Verifying registration...${NC}"
echo ""
docker exec gitlab-sre-spire-server \
    /opt/spire/bin/spire-server entry show \
    -spiffeID spiffe://ravenhelm.local/workload/model-server

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Registration complete!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Ensure SPIRE agent is running on 192.168.50.26"
echo -e "  2. Configure model service to use SPIRE certificates:"
echo -e "     - Cert: /run/spire/certs/svid.pem"
echo -e "     - Key:  /run/spire/certs/key.pem"
echo -e "     - CA:   /run/spire/certs/bundle.pem"
echo -e "  3. Restart Traefik to pick up mTLS configuration:"
echo -e "     docker restart ravenhelm-proxy"
echo -e "  4. Test connection:"
echo -e "     curl https://models.ravenhelm.dev/health"
echo ""
echo -e "${YELLOW}For detailed setup instructions, see:${NC}"
echo -e "  docs/runbooks/RUNBOOK-031-external-model-server-mtls.md"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"


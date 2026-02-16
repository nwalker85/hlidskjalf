#!/bin/bash
# =============================================================================
# Verify External Model Server mTLS Configuration
# =============================================================================
# This script verifies that the external model server is properly configured
# for mTLS authentication via SPIRE.
#
# Usage:
#   ./scripts/verify-model-server-mtls.sh
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     External Model Server mTLS Verification                  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check 1: SPIRE Server Health
echo -e "${YELLOW}[1/8] Checking SPIRE server health...${NC}"
if docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server healthcheck &>/dev/null; then
    echo -e "${GREEN}✓ SPIRE server is healthy${NC}"
else
    echo -e "${RED}✗ SPIRE server is not healthy${NC}"
    ((ERRORS++))
fi
echo ""

# Check 2: SPIRE Agent Registration
echo -e "${YELLOW}[2/8] Checking SPIRE agent registration...${NC}"
if docker exec gitlab-sre-spire-server \
    /opt/spire/bin/spire-server entry show \
    -spiffeID spiffe://ravenhelm.local/agent/model-server 2>/dev/null | grep -q "spiffe://ravenhelm.local/agent/model-server"; then
    echo -e "${GREEN}✓ External agent is registered${NC}"
else
    echo -e "${YELLOW}⚠ External agent not registered (may not be needed for Option B)${NC}"
    ((WARNINGS++))
fi
echo ""

# Check 3: Model Server Workload Registration
echo -e "${YELLOW}[3/8] Checking model server workload registration...${NC}"
if docker exec gitlab-sre-spire-server \
    /opt/spire/bin/spire-server entry show \
    -spiffeID spiffe://ravenhelm.local/workload/model-server 2>/dev/null | grep -q "spiffe://ravenhelm.local/workload/model-server"; then
    echo -e "${GREEN}✓ Model server workload is registered${NC}"
    
    # Show details
    echo -e "${BLUE}Entry details:${NC}"
    docker exec gitlab-sre-spire-server \
        /opt/spire/bin/spire-server entry show \
        -spiffeID spiffe://ravenhelm.local/workload/model-server 2>/dev/null | head -10
else
    echo -e "${RED}✗ Model server workload not registered${NC}"
    echo -e "${YELLOW}  Run: ./scripts/register-model-server-spire.sh${NC}"
    ((ERRORS++))
fi
echo ""

# Check 4: Traefik SPIRE Certificates
echo -e "${YELLOW}[4/8] Checking Traefik SPIRE certificates...${NC}"
if docker exec ravenhelm-traefik test -f /run/spire/certs/svid.pem 2>/dev/null; then
    echo -e "${GREEN}✓ Traefik has SVID certificate${NC}"
    
    # Check expiry
    EXPIRY=$(docker exec ravenhelm-traefik openssl x509 -in /run/spire/certs/svid.pem -noout -enddate 2>/dev/null | cut -d= -f2)
    echo -e "${BLUE}  Certificate expires: $EXPIRY${NC}"
else
    echo -e "${RED}✗ Traefik missing SVID certificate${NC}"
    ((ERRORS++))
fi
echo ""

# Check 5: Traefik Configuration
echo -e "${YELLOW}[5/8] Checking Traefik configuration...${NC}"

# Check serversTransport
if docker exec ravenhelm-traefik cat /etc/traefik/dynamic.yml 2>/dev/null | grep -q "model-server-transport"; then
    echo -e "${GREEN}✓ model-server-transport configured${NC}"
else
    echo -e "${RED}✗ model-server-transport not found in dynamic.yml${NC}"
    ((ERRORS++))
fi

# Check router
if docker exec ravenhelm-traefik cat /etc/traefik/dynamic.yml 2>/dev/null | grep -A 5 "model-server:" | grep -q "models.ravenhelm.dev"; then
    echo -e "${GREEN}✓ Router configured for models.ravenhelm.dev${NC}"
else
    echo -e "${RED}✗ Router not properly configured${NC}"
    ((ERRORS++))
fi

# Check service
if docker exec ravenhelm-traefik cat /etc/traefik/dynamic.yml 2>/dev/null | grep -A 3 "model-server-svc:" | grep -q "192.168.50.26:6701"; then
    echo -e "${GREEN}✓ Service configured for 192.168.50.26:6701${NC}"
    
    # Check if HTTPS
    if docker exec ravenhelm-traefik cat /etc/traefik/dynamic.yml 2>/dev/null | grep -A 3 "model-server-svc:" | grep -q "https://"; then
        echo -e "${GREEN}✓ Service uses HTTPS${NC}"
    else
        echo -e "${YELLOW}⚠ Service uses HTTP (should be HTTPS for mTLS)${NC}"
        ((WARNINGS++))
    fi
else
    echo -e "${RED}✗ Service not properly configured${NC}"
    ((ERRORS++))
fi
echo ""

# Check 6: Port Registry
echo -e "${YELLOW}[6/8] Checking port registry...${NC}"
if grep -q "6701" config/port_registry.yaml 2>/dev/null; then
    echo -e "${GREEN}✓ Port 6701 registered${NC}"
    
    # Show entry
    echo -e "${BLUE}Registry entry:${NC}"
    grep -A 6 "port: 6701" config/port_registry.yaml | head -7
else
    echo -e "${RED}✗ Port 6701 not in registry${NC}"
    ((ERRORS++))
fi
echo ""

# Check 7: Network Connectivity
echo -e "${YELLOW}[7/8] Checking network connectivity...${NC}"
if docker exec ravenhelm-traefik nc -zv 192.168.50.26 6701 2>&1 | grep -q "succeeded"; then
    echo -e "${GREEN}✓ Can reach 192.168.50.26:6701${NC}"
else
    echo -e "${RED}✗ Cannot reach 192.168.50.26:6701${NC}"
    echo -e "${YELLOW}  Check firewall and network configuration${NC}"
    ((ERRORS++))
fi
echo ""

# Check 8: End-to-End Test
echo -e "${YELLOW}[8/8] Testing end-to-end connection...${NC}"

# Try to connect (this will fail if external machine not configured yet)
if timeout 5 docker exec ravenhelm-traefik curl -sf -H "Host: models.ravenhelm.dev" https://192.168.50.26:6701/health &>/dev/null; then
    echo -e "${GREEN}✓ End-to-end mTLS connection successful!${NC}"
elif timeout 5 docker exec ravenhelm-traefik curl -sf -H "Host: models.ravenhelm.dev" https://192.168.50.26:6701/v1/models &>/dev/null; then
    echo -e "${GREEN}✓ End-to-end mTLS connection successful!${NC}"
else
    echo -e "${YELLOW}⚠ Cannot connect to model server${NC}"
    echo -e "${YELLOW}  This is expected if the external machine is not configured yet${NC}"
    echo -e "${YELLOW}  Follow: .model-server-quick-start.md${NC}"
    ((WARNINGS++))
fi
echo ""

# Summary
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo -e "${GREEN}  Configuration is ready for deployment.${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Configuration complete with $WARNINGS warning(s)${NC}"
    echo -e "${YELLOW}  Review warnings above.${NC}"
    exit 0
else
    echo -e "${RED}✗ Found $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    echo -e "${RED}  Fix errors before deployment.${NC}"
    exit 1
fi


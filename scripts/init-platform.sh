#!/bin/bash
# =============================================================================
# Ravenhelm Platform Initialization
# =============================================================================
# Run this ONCE before starting the platform for the first time.
# Creates volumes with correct ownership for the ravenhelm platform user.
#
# Platform User: ravenhelm
# UID: 1001
# GID: 1001
#
# This maps to Kubernetes fsGroup: 1001 for production parity.
# =============================================================================

set -e

# Platform user constants
RAVENHELM_UID=1001
RAVENHELM_GID=1001

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║           RAVENHELM PLATFORM INITIALIZATION                    ║${NC}"
echo -e "${YELLOW}║                                                                ║${NC}"
echo -e "${YELLOW}║   Platform User: ravenhelm (${RAVENHELM_UID}:${RAVENHELM_GID})                          ║${NC}"
echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Certificate volumes (SPIRE SVIDs)
CERT_VOLUMES=(
    "postgres_certs"
    "redis_certs"
    "nats_certs"
)

# Data volumes
DATA_VOLUMES=(
    "postgres_data"
    "redis_data"
    "nats_data"
    "grafana_data"
    "prometheus_data"
    "loki_data"
    "tempo_data"
    "langfuse_data"
    "openbao_data"
    "zitadel_data"
)

# Function to initialize a volume
init_volume() {
    local volume_name="hlidskjalf_$1"
    
    # Create volume if it doesn't exist
    if ! docker volume inspect "$volume_name" >/dev/null 2>&1; then
        docker volume create "$volume_name" >/dev/null
        echo -e "  ${GREEN}Created${NC} $volume_name"
    fi
    
    # Set ownership
    docker run --rm \
        -v "${volume_name}:/vol" \
        alpine chown ${RAVENHELM_UID}:${RAVENHELM_GID} /vol 2>/dev/null
    
    echo -e "  ${GREEN}✓${NC} $1 → ${RAVENHELM_UID}:${RAVENHELM_GID}"
}

# Initialize certificate volumes
echo -e "${YELLOW}Initializing certificate volumes...${NC}"
for vol in "${CERT_VOLUMES[@]}"; do
    init_volume "$vol"
done
echo ""

# Initialize data volumes
echo -e "${YELLOW}Initializing data volumes...${NC}"
for vol in "${DATA_VOLUMES[@]}"; do
    init_volume "$vol"
done
echo ""

# Register SPIRE entry for ravenhelm user
echo -e "${YELLOW}Registering SPIRE entry for ravenhelm user...${NC}"
if docker ps --format '{{.Names}}' | grep -q "gitlab-sre-spire-server"; then
    # Check if entry already exists
    if docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry show 2>/dev/null | grep -q "unix:uid:${RAVENHELM_UID}"; then
        echo -e "  ${GREEN}✓${NC} SPIRE entry for uid:${RAVENHELM_UID} already exists"
    else
        docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server entry create \
            -parentID spiffe://ravenhelm.local/agent/local \
            -spiffeID spiffe://ravenhelm.local/workload/platform \
            -selector unix:uid:${RAVENHELM_UID} \
            >/dev/null 2>&1 && \
        echo -e "  ${GREEN}✓${NC} Registered SPIRE entry for uid:${RAVENHELM_UID}" || \
        echo -e "  ${YELLOW}⚠${NC} Could not register SPIRE entry (SPIRE may not be running)"
    fi
else
    echo -e "  ${YELLOW}⚠${NC} SPIRE server not running - skipping entry registration"
    echo -e "  ${YELLOW}  Run this script again after starting SPIRE${NC}"
fi
echo ""

# Summary
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    INITIALIZATION COMPLETE                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Start SPIRE:    ${YELLOW}docker compose up -d spire-server spire-agent${NC}"
echo -e "  2. Run init again: ${YELLOW}./scripts/init-platform.sh${NC}  (to register SPIRE entry)"
echo -e "  3. Start platform: ${YELLOW}docker compose up -d${NC}"
echo ""


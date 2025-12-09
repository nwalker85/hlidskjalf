#!/bin/bash
# =============================================================================
# SPIRE Bootstrap Script
# Generates upstream CA, creates join tokens, and registers workloads
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="${SCRIPT_DIR}/server"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  SPIRE Bootstrap for Ravenhelm${NC}"
echo -e "${GREEN}========================================${NC}"

# Generate upstream CA if it doesn't exist
if [ ! -f "${SERVER_DIR}/dummy_upstream_ca.key" ]; then
    echo -e "${YELLOW}Generating upstream CA...${NC}"
    
    openssl req -x509 -newkey rsa:4096 \
        -keyout "${SERVER_DIR}/dummy_upstream_ca.key" \
        -out "${SERVER_DIR}/dummy_upstream_ca.crt" \
        -days 365 \
        -nodes \
        -subj "/C=US/O=Ravenhelm/CN=Ravenhelm Root CA" \
        2>/dev/null
    
    echo -e "${GREEN}✓ Upstream CA generated${NC}"
else
    echo -e "${GREEN}✓ Upstream CA already exists${NC}"
fi

# Wait for SPIRE server to be healthy
wait_for_spire_server() {
    echo -e "${YELLOW}Waiting for SPIRE server...${NC}"
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker exec gitlab-sre-spire-server /opt/spire/bin/spire-server healthcheck 2>/dev/null; then
            echo -e "${GREEN}✓ SPIRE server is healthy${NC}"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    echo -e "${RED}✗ SPIRE server failed to become healthy${NC}"
    return 1
}

# Generate join token for agent
generate_join_token() {
    echo -e "${YELLOW}Generating join token for agent...${NC}"
    
    # macOS-compatible token extraction (no grep -P)
    local token=$(docker exec gitlab-sre-spire-server \
        /opt/spire/bin/spire-server token generate \
        -spiffeID spiffe://ravenhelm.local/agent/local \
        -ttl 3600 2>/dev/null | grep "Token:" | sed 's/Token: //')
    
    if [ -n "$token" ]; then
        echo "$token" > "${SCRIPT_DIR}/agent/join_token"
        echo -e "${GREEN}✓ Join token generated: ${token}${NC}"
        echo -e "${YELLOW}To start agent with this token:${NC}"
        echo -e "  SPIRE_JOIN_TOKEN=\"${token}\" docker compose up -d spire-agent"
    else
        echo -e "${RED}✗ Failed to generate join token${NC}"
        return 1
    fi
}

# Register platform workloads
register_workloads() {
    echo -e "${YELLOW}Registering platform workloads...${NC}"
    
    local workloads=(
        # Core Infrastructure
        "postgres:spiffe://ravenhelm.local/workload/postgres"
        "redis:spiffe://ravenhelm.local/workload/redis"
        "nats:spiffe://ravenhelm.local/workload/nats"
        "redpanda:spiffe://ravenhelm.local/workload/redpanda"
        
        # Observability
        "otel-collector:spiffe://ravenhelm.local/workload/otel-collector"
        "prometheus:spiffe://ravenhelm.local/workload/prometheus"
        "grafana:spiffe://ravenhelm.local/workload/grafana"
        "langfuse:spiffe://ravenhelm.local/workload/langfuse"
        "phoenix:spiffe://ravenhelm.local/workload/phoenix"
        "loki:spiffe://ravenhelm.local/workload/loki"
        "tempo:spiffe://ravenhelm.local/workload/tempo"
        
        # DevOps
        "gitlab:spiffe://ravenhelm.local/workload/gitlab"
        "openbao:spiffe://ravenhelm.local/workload/openbao"
        "localstack:spiffe://ravenhelm.local/workload/localstack"
        
        # AI & Control Plane
        "control-plane:spiffe://ravenhelm.local/workload/control-plane"
        "ai-agent:spiffe://ravenhelm.local/workload/norns"
        "ai-local:spiffe://ravenhelm.local/workload/ollama"
        
        # Voice & External
        "voice:spiffe://ravenhelm.local/workload/livekit"
        "external-integration:spiffe://ravenhelm.local/workload/bifrost"
        
        # Graph DBs
        "graph:spiffe://ravenhelm.local/workload/neo4j"
        "graph:spiffe://ravenhelm.local/workload/memgraph"
        
        # External Services (require separate agent setup)
        # See scripts/register-model-server-spire.sh for external model server
        # "model-server:spiffe://ravenhelm.local/workload/model-server"
    )
    
    for workload in "${workloads[@]}"; do
        IFS=':' read -r name spiffe_id <<< "$workload"
        
        docker exec gitlab-sre-spire-server \
            /opt/spire/bin/spire-server entry create \
            -parentID spiffe://ravenhelm.local/agent/local \
            -spiffeID "$spiffe_id" \
            -selector "docker:label:ravenhelm.workload:$name" \
            2>/dev/null || true
        
        echo -e "  ${GREEN}✓ Registered: $name${NC}"
    done
}

# Main execution
case "${1:-}" in
    "ca")
        # Just generate CA (for initial setup before docker-compose up)
        if [ ! -f "${SERVER_DIR}/dummy_upstream_ca.key" ]; then
            openssl req -x509 -newkey rsa:4096 \
                -keyout "${SERVER_DIR}/dummy_upstream_ca.key" \
                -out "${SERVER_DIR}/dummy_upstream_ca.crt" \
                -days 365 \
                -nodes \
                -subj "/C=US/O=Ravenhelm/CN=Ravenhelm Root CA" \
                2>/dev/null
            echo -e "${GREEN}✓ Upstream CA generated${NC}"
        fi
        ;;
    "bootstrap")
        wait_for_spire_server
        generate_join_token
        register_workloads
        ;;
    *)
        echo "Usage: $0 {ca|bootstrap}"
        echo ""
        echo "Commands:"
        echo "  ca        - Generate upstream CA (run before docker-compose up)"
        echo "  bootstrap - Bootstrap SPIRE after server is running"
        exit 1
        ;;
esac

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  SPIRE Bootstrap Complete${NC}"
echo -e "${GREEN}========================================${NC}"


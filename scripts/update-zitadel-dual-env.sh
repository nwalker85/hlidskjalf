#!/usr/bin/env bash
#
# Update Zitadel applications for dual-environment support
# Adds .dev (staging) redirect URIs to existing applications
#
# Usage: ./scripts/update-zitadel-dual-env.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment variables
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    source "${PROJECT_ROOT}/.env"
fi

ZITADEL_URL="${ZITADEL_URL:-https://zitadel.ravenhelm.dev}"
ZITADEL_TOKEN="${ZITADEL_SERVICE_ACCOUNT_TOKEN:-}"

if [[ -z "$ZITADEL_TOKEN" ]]; then
    echo -e "${RED}Error: ZITADEL_SERVICE_ACCOUNT_TOKEN not set${NC}"
    echo "Please set it in .env or pass as environment variable"
    exit 1
fi

# Get project ID
get_project_id() {
    local project_name="$1"
    
    curl -s -X POST "${ZITADEL_URL}/management/v1/projects/_search" \
        -H "Authorization: Bearer ${ZITADEL_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"queries\": [{\"nameQuery\": {\"name\": \"${project_name}\", \"method\": \"TEXT_QUERY_METHOD_EQUALS\"}}]}" \
        | jq -r '.result[0].id // empty'
}

# Get application ID by name
get_app_id() {
    local project_id="$1"
    local app_name="$2"
    
    curl -s "${ZITADEL_URL}/management/v1/projects/${project_id}/apps/_search" \
        -H "Authorization: Bearer ${ZITADEL_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"queries\": [{\"nameQuery\": {\"name\": \"${app_name}\", \"method\": \"TEXT_QUERY_METHOD_EQUALS\"}}]}" \
        | jq -r '.result[0].id // empty'
}

# Get current application config
get_app_config() {
    local project_id="$1"
    local app_id="$2"
    
    curl -s "${ZITADEL_URL}/management/v1/projects/${project_id}/apps/${app_id}" \
        -H "Authorization: Bearer ${ZITADEL_TOKEN}"
}

# Update OIDC application with additional redirect URIs
update_oidc_app() {
    local project_id="$1"
    local app_id="$2"
    local redirect_uris="$3"
    local post_logout_uris="$4"
    
    echo -e "${BLUE}Updating application ${app_id}...${NC}"
    
    local response=$(curl -s -w "\n%{http_code}" -X PUT \
        "${ZITADEL_URL}/management/v1/projects/${project_id}/apps/${app_id}/oidc_config" \
        -H "Authorization: Bearer ${ZITADEL_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
            \"redirectUris\": ${redirect_uris},
            \"postLogoutRedirectUris\": ${post_logout_uris}
        }")
    
    local body=$(echo "$response" | head -n -1)
    local status=$(echo "$response" | tail -n 1)
    
    if [[ "$status" == "200" ]]; then
        echo -e "${GREEN}✓ Successfully updated${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed with status ${status}${NC}"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        return 1
    fi
}

# Main execution
main() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}  Zitadel Dual-Environment Configuration${NC}"
    echo -e "${BLUE}  Adding .dev (staging) redirect URIs${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
    
    # Get project ID
    echo -e "${YELLOW}→ Finding Ravenhelm Platform project...${NC}"
    PROJECT_ID=$(get_project_id "Ravenhelm Platform")
    
    if [[ -z "$PROJECT_ID" ]]; then
        echo -e "${RED}✗ Project 'Ravenhelm Platform' not found${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Found project ID: ${PROJECT_ID}${NC}"
    echo ""
    
    # =========================================================================
    # Grafana
    # =========================================================================
    echo -e "${YELLOW}→ Updating Grafana application...${NC}"
    
    GRAFANA_APP_ID=$(get_app_id "$PROJECT_ID" "Grafana")
    if [[ -z "$GRAFANA_APP_ID" ]]; then
        echo -e "${RED}✗ Grafana application not found${NC}"
    else
        echo -e "${GREEN}✓ Found Grafana app ID: ${GRAFANA_APP_ID}${NC}"
        
        # Add both .test and .dev redirect URIs
        GRAFANA_REDIRECTS='[
            "https://grafana.observe.ravenhelm.test/login/generic_oauth",
            "https://grafana.ravenhelm.test/login/generic_oauth",
            "https://grafana.ravenhelm.dev/login/generic_oauth"
        ]'
        
        GRAFANA_LOGOUT='[
            "https://grafana.observe.ravenhelm.test",
            "https://grafana.ravenhelm.test",
            "https://grafana.ravenhelm.dev"
        ]'
        
        update_oidc_app "$PROJECT_ID" "$GRAFANA_APP_ID" "$GRAFANA_REDIRECTS" "$GRAFANA_LOGOUT"
    fi
    echo ""
    
    # =========================================================================
    # Hlidskjalf UI (NextAuth)
    # =========================================================================
    echo -e "${YELLOW}→ Updating Hlidskjalf UI application...${NC}"
    
    HLIDSKJALF_APP_ID=$(get_app_id "$PROJECT_ID" "Hlidskjalf UI (NextAuth)")
    if [[ -z "$HLIDSKJALF_APP_ID" ]]; then
        echo -e "${YELLOW}⚠ Hlidskjalf UI (NextAuth) not found, trying 'Hlidskjalf UI'...${NC}"
        HLIDSKJALF_APP_ID=$(get_app_id "$PROJECT_ID" "Hlidskjalf UI")
    fi
    
    if [[ -z "$HLIDSKJALF_APP_ID" ]]; then
        echo -e "${RED}✗ Hlidskjalf UI application not found${NC}"
    else
        echo -e "${GREEN}✓ Found Hlidskjalf UI app ID: ${HLIDSKJALF_APP_ID}${NC}"
        
        # Add both .test and .dev redirect URIs
        HLIDSKJALF_REDIRECTS='[
            "https://hlidskjalf.ravenhelm.test/api/auth/callback/zitadel",
            "https://hlidskjalf.ravenhelm.dev/api/auth/callback/zitadel"
        ]'
        
        HLIDSKJALF_LOGOUT='[
            "https://hlidskjalf.ravenhelm.test",
            "https://hlidskjalf.ravenhelm.dev"
        ]'
        
        update_oidc_app "$PROJECT_ID" "$HLIDSKJALF_APP_ID" "$HLIDSKJALF_REDIRECTS" "$HLIDSKJALF_LOGOUT"
    fi
    echo ""
    
    # =========================================================================
    # OAuth2-Proxy (already updated in previous script)
    # =========================================================================
    echo -e "${YELLOW}→ Checking OAuth2-Proxy applications...${NC}"
    
    OAUTH2_APP_ID=$(get_app_id "$PROJECT_ID" "OAuth2-Proxy")
    if [[ -z "$OAUTH2_APP_ID" ]]; then
        echo -e "${YELLOW}⚠ OAuth2-Proxy application not found${NC}"
    else
        echo -e "${GREEN}✓ Found OAuth2-Proxy app ID: ${OAUTH2_APP_ID}${NC}"
        echo -e "  ${BLUE}(This should already be configured for both .test and .dev)${NC}"
    fi
    echo ""
    
    # =========================================================================
    # Redpanda Console
    # =========================================================================
    echo -e "${YELLOW}→ Updating Redpanda Console application...${NC}"
    
    REDPANDA_APP_ID=$(get_app_id "$PROJECT_ID" "Redpanda Console")
    if [[ -z "$REDPANDA_APP_ID" ]]; then
        echo -e "${YELLOW}⚠ Redpanda Console application not found${NC}"
    else
        echo -e "${GREEN}✓ Found Redpanda Console app ID: ${REDPANDA_APP_ID}${NC}"
        
        REDPANDA_REDIRECTS='[
            "https://redpanda.ravenhelm.test/api/oidc/callback",
            "https://redpanda.ravenhelm.dev/api/oidc/callback"
        ]'
        
        REDPANDA_LOGOUT='[
            "https://redpanda.ravenhelm.test",
            "https://redpanda.ravenhelm.dev"
        ]'
        
        update_oidc_app "$PROJECT_ID" "$REDPANDA_APP_ID" "$REDPANDA_REDIRECTS" "$REDPANDA_LOGOUT"
    fi
    echo ""
    
    # =========================================================================
    # Summary
    # =========================================================================
    echo -e "${BLUE}================================================${NC}"
    echo -e "${GREEN}✓ Dual-environment configuration complete${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
    echo -e "Applications now support both:"
    echo -e "  • ${YELLOW}.test${NC} domain (dev environment)"
    echo -e "  • ${YELLOW}.dev${NC} domain (staging environment)"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "1. Restart Grafana: ${BLUE}docker-compose restart grafana${NC}"
    echo -e "2. Test SSO at: ${BLUE}https://grafana.ravenhelm.dev${NC}"
    echo -e "3. Test SSO at: ${BLUE}https://hlidskjalf.ravenhelm.dev${NC}"
    echo ""
}

# Run main function
main "$@"


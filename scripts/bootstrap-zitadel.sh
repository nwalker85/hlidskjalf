#!/bin/bash
# =============================================================================
# Zitadel Bootstrap Script
# =============================================================================
# Uses the Skuld service account to create OIDC applications for all services
# via the Zitadel Management API.
#
# Prerequisites:
#   - Zitadel running at https://zitadel.ravenhelm.test
#   - Skuld service account token in .env
# =============================================================================

set -e

# Load environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

# Configuration
ZITADEL_URL="${ZITADEL_ISSUER:-https://zitadel.ravenhelm.test}"
TOKEN="${ZITADEL_SERVICE_ACCOUNT_TOKEN}"

if [ -z "$TOKEN" ]; then
    echo "❌ ZITADEL_SERVICE_ACCOUNT_TOKEN not set in .env"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           ZITADEL BOOTSTRAP - OIDC Applications                 ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "Zitadel URL: $ZITADEL_URL"
echo ""

# Helper function for API calls
zitadel_api() {
    local method=$1
    local endpoint=$2
    local data=$3
    
    if [ -n "$data" ]; then
        curl -sk -X "$method" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "${ZITADEL_URL}${endpoint}"
    else
        curl -sk -X "$method" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            "${ZITADEL_URL}${endpoint}"
    fi
}

# Output file for generated credentials
CREDS_FILE="$PROJECT_ROOT/.zitadel-apps.env"
echo "# Zitadel OIDC Application Credentials" > "$CREDS_FILE"
echo "# Generated: $(date)" >> "$CREDS_FILE"
echo "" >> "$CREDS_FILE"

# =============================================================================
# Step 1: Create Project
# =============================================================================
echo "📦 Creating Ravenhelm project..."

PROJECT_RESPONSE=$(zitadel_api POST "/management/v1/projects" '{
    "name": "Ravenhelm Platform",
    "projectRoleAssertion": true,
    "projectRoleCheck": true
}')

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | jq -r '.id // empty')

if [ -z "$PROJECT_ID" ]; then
    echo "   ⚠️  Project may already exist, searching..."
    SEARCH_RESPONSE=$(zitadel_api POST "/management/v1/projects/_search" '{
        "queries": [{"nameQuery": {"name": "Ravenhelm Platform", "method": "TEXT_QUERY_METHOD_EQUALS"}}]
    }')
    PROJECT_ID=$(echo "$SEARCH_RESPONSE" | jq -r '.result[0].id // empty')
fi

if [ -z "$PROJECT_ID" ]; then
    echo "   ❌ Failed to create or find project"
    exit 1
fi

echo "   ✅ Project ID: $PROJECT_ID"
echo "" >> "$CREDS_FILE"
echo "ZITADEL_PROJECT_ID=$PROJECT_ID" >> "$CREDS_FILE"

# =============================================================================
# Step 2: Create OIDC Applications
# =============================================================================

create_oidc_app() {
    local app_name=$1
    local app_type=$2  # OIDC_APP_TYPE_WEB, OIDC_APP_TYPE_USER_AGENT, OIDC_APP_TYPE_NATIVE
    local auth_method=$3  # OIDC_AUTH_METHOD_TYPE_BASIC, OIDC_AUTH_METHOD_TYPE_POST, OIDC_AUTH_METHOD_TYPE_NONE
    local redirect_uris=$4  # JSON array
    local logout_uris=$5  # JSON array
    local env_prefix=$6
    
    echo "🔧 Creating $app_name..."
    
    APP_RESPONSE=$(zitadel_api POST "/management/v1/projects/$PROJECT_ID/apps/oidc" "{
        \"name\": \"$app_name\",
        \"redirectUris\": $redirect_uris,
        \"responseTypes\": [\"OIDC_RESPONSE_TYPE_CODE\"],
        \"grantTypes\": [\"OIDC_GRANT_TYPE_AUTHORIZATION_CODE\", \"OIDC_GRANT_TYPE_REFRESH_TOKEN\"],
        \"appType\": \"$app_type\",
        \"authMethodType\": \"$auth_method\",
        \"postLogoutRedirectUris\": $logout_uris,
        \"devMode\": true,
        \"accessTokenType\": \"OIDC_TOKEN_TYPE_JWT\",
        \"accessTokenRoleAssertion\": true,
        \"idTokenRoleAssertion\": true,
        \"idTokenUserinfoAssertion\": true
    }")
    
    APP_ID=$(echo "$APP_RESPONSE" | jq -r '.appId // empty')
    CLIENT_ID=$(echo "$APP_RESPONSE" | jq -r '.clientId // empty')
    CLIENT_SECRET=$(echo "$APP_RESPONSE" | jq -r '.clientSecret // empty')
    
    if [ -z "$APP_ID" ] || [ "$APP_ID" = "null" ]; then
        echo "   ⚠️  App may already exist or failed to create"
        echo "   Response: $APP_RESPONSE"
        return 1
    fi
    
    echo "   ✅ App ID: $APP_ID"
    echo "   ✅ Client ID: $CLIENT_ID"
    
    # Save to credentials file
    echo "" >> "$CREDS_FILE"
    echo "# $app_name" >> "$CREDS_FILE"
    echo "${env_prefix}_CLIENT_ID=$CLIENT_ID" >> "$CREDS_FILE"
    if [ -n "$CLIENT_SECRET" ] && [ "$CLIENT_SECRET" != "null" ]; then
        echo "${env_prefix}_CLIENT_SECRET=$CLIENT_SECRET" >> "$CREDS_FILE"
    fi
    
    return 0
}

# -----------------------------------------------------------------------------
# Grafana
# -----------------------------------------------------------------------------
create_oidc_app \
    "Grafana" \
    "OIDC_APP_TYPE_WEB" \
    "OIDC_AUTH_METHOD_TYPE_BASIC" \
    '["https://grafana.observe.ravenhelm.test/login/generic_oauth"]' \
    '["https://grafana.observe.ravenhelm.test"]' \
    "GRAFANA_OIDC"

# -----------------------------------------------------------------------------
# GitLab
# -----------------------------------------------------------------------------
create_oidc_app \
    "GitLab" \
    "OIDC_APP_TYPE_WEB" \
    "OIDC_AUTH_METHOD_TYPE_BASIC" \
    '["https://gitlab.ravenhelm.test/users/auth/openid_connect/callback"]' \
    '["https://gitlab.ravenhelm.test"]' \
    "GITLAB_OIDC"

# -----------------------------------------------------------------------------
# Vault (OpenBao)
# -----------------------------------------------------------------------------
create_oidc_app \
    "Vault" \
    "OIDC_APP_TYPE_WEB" \
    "OIDC_AUTH_METHOD_TYPE_BASIC" \
    '["https://vault.ravenhelm.test/ui/vault/auth/oidc/oidc/callback", "http://localhost:8250/oidc/callback"]' \
    '["https://vault.ravenhelm.test/ui/vault/auth/oidc/oidc/callback"]' \
    "VAULT_OIDC"

# -----------------------------------------------------------------------------
# Hlidskjalf UI (SPA - no client secret)
# -----------------------------------------------------------------------------
create_oidc_app \
    "Hlidskjalf UI" \
    "OIDC_APP_TYPE_USER_AGENT" \
    "OIDC_AUTH_METHOD_TYPE_NONE" \
    '["https://hlidskjalf.ravenhelm.test/callback", "https://hlidskjalf.ravenhelm.test/silent-renew"]' \
    '["https://hlidskjalf.ravenhelm.test"]' \
    "HLIDSKJALF_OIDC"

# -----------------------------------------------------------------------------
# n8n
# -----------------------------------------------------------------------------
create_oidc_app \
    "n8n" \
    "OIDC_APP_TYPE_WEB" \
    "OIDC_AUTH_METHOD_TYPE_BASIC" \
    '["https://n8n.ravenhelm.test/rest/oauth2-credential/callback"]' \
    '["https://n8n.ravenhelm.test"]' \
    "N8N_OIDC"

# -----------------------------------------------------------------------------
# Redpanda Console
# -----------------------------------------------------------------------------
create_oidc_app \
    "Redpanda Console" \
    "OIDC_APP_TYPE_WEB" \
    "OIDC_AUTH_METHOD_TYPE_BASIC" \
    '["https://events.ravenhelm.test/auth/callback"]' \
    '["https://events.ravenhelm.test"]' \
    "REDPANDA_OIDC"

# -----------------------------------------------------------------------------
# Langfuse
# -----------------------------------------------------------------------------
create_oidc_app \
    "Langfuse" \
    "OIDC_APP_TYPE_WEB" \
    "OIDC_AUTH_METHOD_TYPE_BASIC" \
    '["https://langfuse.observe.ravenhelm.test/api/auth/callback/custom"]' \
    '["https://langfuse.observe.ravenhelm.test"]' \
    "LANGFUSE_OIDC"

# -----------------------------------------------------------------------------
# Phoenix (Arize)
# -----------------------------------------------------------------------------
create_oidc_app \
    "Phoenix" \
    "OIDC_APP_TYPE_WEB" \
    "OIDC_AUTH_METHOD_TYPE_BASIC" \
    '["https://phoenix.observe.ravenhelm.test/auth/callback"]' \
    '["https://phoenix.observe.ravenhelm.test"]' \
    "PHOENIX_OIDC"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    BOOTSTRAP COMPLETE                            ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "📄 Credentials saved to: $CREDS_FILE"
echo ""
echo "Next steps:"
echo "  1. Review the generated credentials in $CREDS_FILE"
echo "  2. Update each service's configuration with OIDC settings"
echo "  3. Restart services to apply SSO"
echo ""
echo "Common OIDC Configuration:"
echo "  Issuer:     $ZITADEL_URL"
echo "  Auth URL:   $ZITADEL_URL/oauth/v2/authorize"
echo "  Token URL:  $ZITADEL_URL/oauth/v2/token"
echo "  JWKS URL:   $ZITADEL_URL/oauth/v2/keys"
echo "  Userinfo:   $ZITADEL_URL/oidc/v1/userinfo"
echo ""

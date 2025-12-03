#!/bin/bash
# =============================================================================
# Vault/OpenBao OIDC Bootstrap Script
# =============================================================================
# Configures OIDC auth method in OpenBao using Zitadel as the IdP.
#
# Prerequisites:
#   - OpenBao running and unsealed
#   - Root token available
#   - Zitadel OIDC app credentials in .env
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

# Configuration
VAULT_ADDR="${VAULT_ADDR:-https://vault.ravenhelm.test}"
ZITADEL_URL="${ZITADEL_ISSUER:-https://zitadel.ravenhelm.test}"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           VAULT/OPENBAO OIDC CONFIGURATION                      ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "Vault Address: $VAULT_ADDR"
echo "Zitadel URL: $ZITADEL_URL"
echo ""

# Check for root token
if [ -z "$VAULT_TOKEN" ]; then
    echo "⚠️  VAULT_TOKEN not set. Please provide the root token:"
    read -sp "Root Token: " VAULT_TOKEN
    echo ""
fi

export VAULT_ADDR
export VAULT_TOKEN
export VAULT_SKIP_VERIFY=true  # For self-signed certs

# Check vault status
echo "📋 Checking Vault status..."
if ! bao status 2>/dev/null; then
    echo "❌ Vault is not accessible or is sealed"
    echo "   Please unseal Vault first and try again"
    exit 1
fi

# Enable OIDC auth method
echo "🔧 Enabling OIDC auth method..."
bao auth enable oidc 2>/dev/null || echo "   ⚠️  OIDC auth may already be enabled"

# Configure OIDC auth method
echo "🔧 Configuring OIDC settings..."
bao write auth/oidc/config \
    oidc_discovery_url="$ZITADEL_URL" \
    oidc_client_id="$VAULT_OIDC_CLIENT_ID" \
    oidc_client_secret="$VAULT_OIDC_CLIENT_SECRET" \
    default_role="default"

# Create default role
echo "🔧 Creating default OIDC role..."
bao write auth/oidc/role/default \
    bound_audiences="$VAULT_OIDC_CLIENT_ID" \
    allowed_redirect_uris="https://vault.ravenhelm.test/ui/vault/auth/oidc/oidc/callback" \
    allowed_redirect_uris="http://localhost:8250/oidc/callback" \
    user_claim="sub" \
    groups_claim="groups" \
    policies="default" \
    ttl="1h"

# Create admin role (optional - for users in admin group)
echo "🔧 Creating admin OIDC role..."
bao write auth/oidc/role/admin \
    bound_audiences="$VAULT_OIDC_CLIENT_ID" \
    allowed_redirect_uris="https://vault.ravenhelm.test/ui/vault/auth/oidc/oidc/callback" \
    allowed_redirect_uris="http://localhost:8250/oidc/callback" \
    user_claim="sub" \
    groups_claim="groups" \
    bound_claims='{"groups": ["admin"]}' \
    policies="admin,default" \
    ttl="4h"

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    OIDC CONFIGURATION COMPLETE                   ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "Users can now log in to Vault via:"
echo "  URL: $VAULT_ADDR/ui"
echo "  Method: OIDC"
echo "  Role: default (or admin for privileged users)"
echo ""


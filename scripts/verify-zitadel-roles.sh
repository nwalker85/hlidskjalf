#!/bin/bash
# =============================================================================
# Verify Zitadel Role Claims
# =============================================================================
# This script helps debug OIDC role claims from Zitadel
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

ZITADEL_URL="${ZITADEL_ISSUER:-https://zitadel.ravenhelm.test}"

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           ZITADEL ROLE VERIFICATION                             ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Get user credentials
read -p "Username (e.g., nate@ravenhelm.co): " USERNAME
read -sp "Password: " PASSWORD
echo ""

# Get token with role scope
echo ""
echo "🔑 Getting token with role scope..."
TOKEN_RESPONSE=$(curl -sk -X POST \
    -d "grant_type=password" \
    -d "client_id=${GRAFANA_OIDC_CLIENT_ID}" \
    -d "client_secret=${GRAFANA_OIDC_CLIENT_SECRET}" \
    -d "username=${USERNAME}" \
    -d "password=${PASSWORD}" \
    -d "scope=openid profile email urn:zitadel:iam:org:project:roles" \
    "${ZITADEL_URL}/oauth/v2/token")

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token // empty')
ID_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.id_token // empty')

if [ -z "$ACCESS_TOKEN" ]; then
    echo "❌ Failed to get token"
    echo "$TOKEN_RESPONSE" | jq '.'
    exit 1
fi

echo "✅ Token obtained"
echo ""

# Decode and display ID token claims
echo "📋 ID Token Claims:"
echo "$ID_TOKEN" | cut -d'.' -f2 | base64 -d 2>/dev/null | jq '.' || echo "Failed to decode"
echo ""

# Get userinfo
echo "📋 Userinfo Response:"
curl -sk -H "Authorization: Bearer $ACCESS_TOKEN" \
    "${ZITADEL_URL}/oidc/v1/userinfo" | jq '.'
echo ""

# Check for role claims
echo "🔍 Role Claims:"
ROLES=$(echo "$ID_TOKEN" | cut -d'.' -f2 | base64 -d 2>/dev/null | jq -r '."urn:zitadel:iam:org:project:roles" // "No roles found"')
echo "$ROLES" | jq '.' 2>/dev/null || echo "$ROLES"


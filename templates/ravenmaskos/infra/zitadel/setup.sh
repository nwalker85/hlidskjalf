#!/bin/bash
# Zitadel setup script for RavenMaskOS
# This script configures Zitadel with the necessary project, applications, and actions

set -e

ZITADEL_URL="${ZITADEL_URL:-http://localhost:8085}"
MACHINEKEY_PATH="${MACHINEKEY_PATH:-./machinekey/zitadel-admin-sa.json}"

# Wait for Zitadel to be ready
echo "Waiting for Zitadel to be ready..."
until curl -sf "${ZITADEL_URL}/debug/ready" > /dev/null 2>&1; do
    echo "Zitadel not ready yet, waiting..."
    sleep 5
done
echo "Zitadel is ready!"

# Check if machinekey exists
if [ ! -f "$MACHINEKEY_PATH" ]; then
    echo "Machine key not found at $MACHINEKEY_PATH"
    echo "Make sure to mount the zitadel_machinekey volume"
    exit 1
fi

# Get access token using service account
echo "Authenticating with service account..."
ACCESS_TOKEN=$(curl -sf -X POST "${ZITADEL_URL}/oauth/v2/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer" \
    -d "scope=openid urn:zitadel:iam:org:project:id:zitadel:aud" \
    -d "assertion=$(cat $MACHINEKEY_PATH | python3 -c "
import json
import sys
import time
import jwt

key_data = json.load(sys.stdin)
now = int(time.time())
payload = {
    'iss': key_data['userId'],
    'sub': key_data['userId'],
    'aud': '${ZITADEL_URL}',
    'iat': now,
    'exp': now + 3600
}
token = jwt.encode(payload, key_data['key'], algorithm='RS256', headers={'kid': key_data['keyId']})
print(token)
")" | jq -r '.access_token')

if [ -z "$ACCESS_TOKEN" ] || [ "$ACCESS_TOKEN" = "null" ]; then
    echo "Failed to get access token"
    exit 1
fi

echo "Successfully authenticated!"

# Create project
echo "Creating RavenMaskOS project..."
PROJECT_RESPONSE=$(curl -sf -X POST "${ZITADEL_URL}/management/v1/projects" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "RavenMaskOS",
        "projectRoleAssertion": true,
        "projectRoleCheck": true
    }' 2>/dev/null || echo '{"error": "exists"}')

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | jq -r '.id // empty')
if [ -z "$PROJECT_ID" ]; then
    echo "Project may already exist, fetching..."
    PROJECT_ID=$(curl -sf -X POST "${ZITADEL_URL}/management/v1/projects/_search" \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"queries": [{"nameQuery": {"name": "RavenMaskOS", "method": "TEXT_QUERY_METHOD_EQUALS"}}]}' \
        | jq -r '.result[0].id')
fi

echo "Project ID: $PROJECT_ID"

# Create Web Application (PKCE for SPA)
echo "Creating web application..."
WEB_APP_RESPONSE=$(curl -sf -X POST "${ZITADEL_URL}/management/v1/projects/${PROJECT_ID}/apps/oidc" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "RavenMaskOS Web",
        "redirectUris": [
            "http://localhost:3000/api/auth/callback",
            "http://localhost:3000/auth/callback"
        ],
        "postLogoutRedirectUris": [
            "http://localhost:3000"
        ],
        "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
        "grantTypes": ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN"],
        "appType": "OIDC_APP_TYPE_USER_AGENT",
        "authMethodType": "OIDC_AUTH_METHOD_TYPE_NONE",
        "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
        "idTokenRoleAssertion": true,
        "idTokenUserinfoAssertion": true,
        "clockSkew": "0s",
        "devMode": true
    }' 2>/dev/null || echo '{"error": "exists"}')

WEB_CLIENT_ID=$(echo "$WEB_APP_RESPONSE" | jq -r '.clientId // empty')
echo "Web App Client ID: $WEB_CLIENT_ID"

# Create Backend Application (Client Credentials for API)
echo "Creating backend API application..."
API_APP_RESPONSE=$(curl -sf -X POST "${ZITADEL_URL}/management/v1/projects/${PROJECT_ID}/apps/oidc" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "RavenMaskOS API",
        "grantTypes": ["OIDC_GRANT_TYPE_CLIENT_CREDENTIALS"],
        "appType": "OIDC_APP_TYPE_WEB",
        "authMethodType": "OIDC_AUTH_METHOD_TYPE_BASIC",
        "accessTokenType": "OIDC_TOKEN_TYPE_JWT"
    }' 2>/dev/null || echo '{"error": "exists"}')

API_CLIENT_ID=$(echo "$API_APP_RESPONSE" | jq -r '.clientId // empty')
API_CLIENT_SECRET=$(echo "$API_APP_RESPONSE" | jq -r '.clientSecret // empty')
echo "API App Client ID: $API_CLIENT_ID"

# Create project roles
echo "Creating project roles..."
for role in "admin" "editor" "viewer"; do
    curl -sf -X POST "${ZITADEL_URL}/management/v1/projects/${PROJECT_ID}/roles" \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"roleKey\": \"$role\", \"displayName\": \"$(echo $role | sed 's/./\u&/')\"}" 2>/dev/null || true
done

# Output configuration
echo ""
echo "========================================"
echo "Zitadel Setup Complete!"
echo "========================================"
echo ""
echo "Add these to your .env file:"
echo ""
echo "# Zitadel OIDC Configuration"
echo "ZITADEL_ISSUER=${ZITADEL_URL}"
echo "ZITADEL_PROJECT_ID=${PROJECT_ID}"
echo "ZITADEL_WEB_CLIENT_ID=${WEB_CLIENT_ID}"
if [ -n "$API_CLIENT_ID" ] && [ "$API_CLIENT_ID" != "null" ]; then
    echo "ZITADEL_API_CLIENT_ID=${API_CLIENT_ID}"
    echo "ZITADEL_API_CLIENT_SECRET=${API_CLIENT_SECRET}"
fi
echo ""
echo "Zitadel Console: ${ZITADEL_URL}/ui/console"
echo "Login: admin / Admin123!"
echo ""

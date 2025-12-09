#!/bin/bash
# Deploy External HTTPS with Let's Encrypt for ravenhelm.dev
# See: docs/runbooks/RUNBOOK-026-letsencrypt-external-https.md

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 External HTTPS Deployment for ravenhelm.dev"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ============================================================================
# Step 1: Check Prerequisites
# ============================================================================
echo "📋 Step 1/6: Checking prerequisites..."

# Check .env file exists
if [[ ! -f .env ]]; then
  echo "⚠️  No .env file found. Creating from template..."
  if [[ -f .env.example ]]; then
    cp .env.example .env
  else
    touch .env
  fi
fi

# Check for required env vars
missing_vars=()
if ! grep -q "OAUTH2_PROXY_CLIENT_ID=" .env; then
  missing_vars+=("OAUTH2_PROXY_CLIENT_ID")
fi
if ! grep -q "OAUTH2_PROXY_CLIENT_SECRET=" .env; then
  missing_vars+=("OAUTH2_PROXY_CLIENT_SECRET")
fi
if ! grep -q "OAUTH2_PROXY_COOKIE_SECRET=" .env; then
  missing_vars+=("OAUTH2_PROXY_COOKIE_SECRET")
fi

if [[ ${#missing_vars[@]} -gt 0 ]]; then
  echo "❌ Missing required environment variables in .env:"
  for var in "${missing_vars[@]}"; do
    echo "   - $var"
  done
  echo ""
  echo "Please add them to .env file before continuing."
  exit 1
fi

# Check if oauth2-proxy-dev vars exist, if not, reuse .test credentials
if ! grep -q "OAUTH2_PROXY_DEV_CLIENT_ID=" .env; then
  echo "⚠️  OAUTH2_PROXY_DEV credentials not found."
  echo "   Reusing .test credentials for now..."
  echo ""
  
  # Source existing credentials
  source .env
  
  # Append dev credentials
  cat >> .env << EOF

# OAuth2-Proxy for .dev domain (public HTTPS)
# NOTE: You should create a separate Zitadel application for production
OAUTH2_PROXY_DEV_CLIENT_ID=${OAUTH2_PROXY_CLIENT_ID}
OAUTH2_PROXY_DEV_CLIENT_SECRET=${OAUTH2_PROXY_CLIENT_SECRET}
EOF
  
  echo "✅ Added OAUTH2_PROXY_DEV credentials (reusing .test values)"
fi

# Check DNS resolution
echo ""
echo "🌐 Checking DNS resolution..."
test_domains=("hlidskjalf.ravenhelm.dev" "auth.ravenhelm.dev" "zitadel.ravenhelm.dev" "grafana.ravenhelm.dev")
dns_ok=true

for domain in "${test_domains[@]}"; do
  if host "$domain" > /dev/null 2>&1; then
    ip=$(host "$domain" | awk '/has address/ { print $4 }' | head -1)
    echo "   ✓ $domain → $ip"
  else
    echo "   ✗ $domain (not resolved)"
    dns_ok=false
  fi
done

if [[ "$dns_ok" == "false" ]]; then
  echo ""
  echo "⚠️  Some DNS records are not resolving."
  echo "   Let's Encrypt will fail without proper DNS."
  read -p "Continue anyway? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

echo "✅ Prerequisites checked"

# ============================================================================
# Step 2: Create Let's Encrypt Storage Volume
# ============================================================================
echo ""
echo "📦 Step 2/6: Creating Let's Encrypt storage volume..."

if docker volume inspect ravenhelm-proxy_traefik_letsencrypt > /dev/null 2>&1; then
  echo "   Volume already exists"
else
  cd ravenhelm-proxy
  docker compose up --no-start traefik 2>/dev/null || true
  cd ..
  echo "✅ Volume created"
fi

# ============================================================================
# Step 3: Restart Traefik with Let's Encrypt Config
# ============================================================================
echo ""
echo "🔄 Step 3/6: Restarting Traefik..."

cd ravenhelm-proxy

# Stop Traefik
docker compose down

# Start Traefik (and dependencies)
docker compose up -d

# Wait for Traefik to be healthy
echo "   Waiting for Traefik to be ready..."
timeout=30
count=0
until docker exec ravenhelm-traefik traefik healthcheck > /dev/null 2>&1; do
  sleep 1
  count=$((count + 1))
  if [[ $count -ge $timeout ]]; then
    echo "❌ Traefik failed to start within ${timeout}s"
    docker logs ravenhelm-traefik --tail 20
    exit 1
  fi
done

echo "✅ Traefik restarted"

cd ..

# ============================================================================
# Step 4: Start oauth2-proxy-dev
# ============================================================================
echo ""
echo "🔒 Step 4/6: Starting oauth2-proxy-dev..."

# Check which compose file to use
if [[ -f compose/docker-compose.security.yml ]]; then
  docker compose -f compose/docker-compose.security.yml up -d oauth2-proxy-dev
else
  docker compose up -d oauth2-proxy-dev
fi

# Wait for oauth2-proxy-dev to be ready
echo "   Waiting for oauth2-proxy-dev..."
sleep 3

if docker ps | grep -q gitlab-sre-oauth2-proxy-dev; then
  echo "✅ oauth2-proxy-dev started"
else
  echo "❌ oauth2-proxy-dev failed to start"
  docker logs gitlab-sre-oauth2-proxy-dev --tail 20
  exit 1
fi

# ============================================================================
# Step 5: Verify Services
# ============================================================================
echo ""
echo "🔍 Step 5/6: Verifying services..."

echo ""
echo "Service Status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAME|traefik|oauth2-proxy)" || true

echo ""
echo "Port Listeners:"
for port in 80 443 4180 4181; do
  if lsof -i :$port > /dev/null 2>&1; then
    service=$(lsof -i :$port | awk 'NR==2 {print $1}')
    echo "   ✓ Port $port: $service"
  else
    echo "   ✗ Port $port: (not listening)"
  fi
done

# ============================================================================
# Step 6: Instructions
# ============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 IMPORTANT: Configure Zitadel Redirect URIs"
echo ""
echo "1. Open Zitadel Console:"
echo "   https://zitadel.ravenhelm.test/ui/console"
echo ""
echo "2. Go to your OAuth2-Proxy application and add these redirect URIs:"
echo "   • https://auth.ravenhelm.dev/oauth2/callback"
echo "   • https://hlidskjalf.ravenhelm.dev/*"
echo "   • https://hlidskjalf-api.ravenhelm.dev/*"
echo "   • https://grafana.ravenhelm.dev/login/generic_oauth"
echo ""
echo "3. Also add redirect URIs for Zitadel itself:"
echo "   • https://zitadel.ravenhelm.dev/ui/console/auth/callback"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Testing Commands"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Monitor Traefik logs for ACME challenges:"
echo "  docker logs ravenhelm-traefik -f | grep -i acme"
echo ""
echo "Test HTTPS endpoint (expect staging cert warning):"
echo "  curl -Ik https://hlidskjalf.ravenhelm.dev"
echo ""
echo "Check certificate details:"
echo "  echo | openssl s_client -connect hlidskjalf.ravenhelm.dev:443 2>/dev/null | openssl x509 -noout -issuer -dates"
echo ""
echo "Open in browser (will trigger Let's Encrypt issuance):"
echo "  open https://hlidskjalf.ravenhelm.dev"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚 Next Steps"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Configure Zitadel redirect URIs (see above)"
echo "2. Test staging certificates work correctly"
echo "3. Switch to production Let's Encrypt (see runbook)"
echo "4. Update Hliðskjálf UI NextAuth config for .dev domain"
echo ""
echo "See: docs/runbooks/RUNBOOK-026-letsencrypt-external-https.md"
echo ""


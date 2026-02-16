#!/bin/bash
# Switch Hlidskjalf UI between dev, staging, and production environments
# Usage: ./scripts/switch-hlidskjalf-env.sh [dev|staging|prod]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

ENV=${1:-dev}

case $ENV in
  dev)
    NEXTAUTH_URL="https://hlidskjalf.ravenhelm.test"
    ZITADEL_ISSUER="https://zitadel.ravenhelm.test"
    echo "🔧 Switching to DEVELOPMENT (.test)"
    ;;
  staging)
    NEXTAUTH_URL="https://hlidskjalf.ravenhelm.dev"
    ZITADEL_ISSUER="https://zitadel.ravenhelm.dev"
    echo "🔧 Switching to STAGING (.dev)"
    ;;
  prod)
    NEXTAUTH_URL="https://hlidskjalf.ravenhelm.ai"
    ZITADEL_ISSUER="https://zitadel.ravenhelm.ai"
    echo "🔧 Switching to PRODUCTION (.ai)"
    ;;
  *)
    echo "❌ Invalid environment: $ENV"
    echo "Usage: $0 [dev|staging|prod]"
    exit 1
    ;;
esac

cd "$PROJECT_ROOT"

# Update NEXTAUTH_URL in .env
if grep -q "^NEXTAUTH_URL=" .env 2>/dev/null; then
  sed -i.bak "s|^NEXTAUTH_URL=.*|NEXTAUTH_URL=$NEXTAUTH_URL|" .env
  rm .env.bak
else
  echo "NEXTAUTH_URL=$NEXTAUTH_URL" >> .env
fi

echo "✅ Updated .env: NEXTAUTH_URL=$NEXTAUTH_URL"
echo ""
echo "🔄 Rebuilding and restarting Hlidskjalf UI..."
docker compose up -d --build hlidskjalf-ui

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Environment switched to: $ENV"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "URLs:"
echo "  Hlidskjalf UI:  $NEXTAUTH_URL"
echo "  Zitadel SSO:    $ZITADEL_ISSUER"
echo ""
echo "Test:"
echo "  open $NEXTAUTH_URL"
echo ""


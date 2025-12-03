#!/bin/bash
#
# Ravenhelm Secret Rotation Script
# =================================
# Helper script for rotating secrets stored in AWS Secrets Manager (LocalStack)
#
# Usage:
#   ./scripts/rotate-secrets.sh [secret-type]
#
# See RUNBOOK-010-secret-rotation.md for detailed procedures.
#

set -e

# =========================================================================
# Configuration
# =========================================================================

AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://localhost:4566}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# =========================================================================
# Helper Functions
# =========================================================================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    log "ERROR: $1" >&2
    exit 1
}

aws_cmd() {
    if [ -n "$AWS_ENDPOINT_URL" ]; then
        aws --endpoint-url "$AWS_ENDPOINT_URL" --region "$AWS_REGION" "$@"
    else
        aws --region "$AWS_REGION" "$@"
    fi
}

generate_password() {
    openssl rand -base64 32 | tr -d '=+/' | head -c 32
}

# =========================================================================
# Rotation Functions
# =========================================================================

rotate_api_key() {
    local provider=$1
    local secret_name="ravenhelm/dev/${provider}_api_key"
    
    log "Rotating $provider API key..."
    log "Current secret: $secret_name"
    
    # Show current value (masked)
    current=$(aws_cmd secretsmanager get-secret-value \
        --secret-id "$secret_name" \
        --query 'SecretString' --output text 2>/dev/null || echo "NOT_SET")
    
    if [ "$current" != "NOT_SET" ]; then
        log "Current key: ${current:0:10}...${current: -4}"
    fi
    
    echo ""
    read -p "Enter new $provider API key (or 'skip' to cancel): " NEW_KEY
    
    if [ "$NEW_KEY" == "skip" ] || [ -z "$NEW_KEY" ]; then
        log "Skipped rotation for $provider"
        return
    fi
    
    aws_cmd secretsmanager put-secret-value \
        --secret-id "$secret_name" \
        --secret-string "$NEW_KEY"
    
    log "✓ Secret updated: $secret_name"
    log ""
    log "Next steps:"
    log "  1. Restart dependent services:"
    log "     docker compose restart hlidskjalf langgraph"
    log "  2. Verify health:"
    log "     curl -s https://hlidskjalf.ravenhelm.test/health"
}

rotate_postgres() {
    log "Rotating PostgreSQL password..."
    
    NEW_PASSWORD=$(generate_password)
    log "Generated new password: ${NEW_PASSWORD:0:4}...${NEW_PASSWORD: -4}"
    
    # Update PostgreSQL user
    log "Updating PostgreSQL user password..."
    docker exec -it gitlab-sre-postgres psql -U postgres -c \
        "ALTER USER ravenhelm PASSWORD '$NEW_PASSWORD';" 2>/dev/null || \
        error "Failed to update PostgreSQL password. Is the container running?"
    
    # Update Secrets Manager
    log "Updating Secrets Manager..."
    aws_cmd secretsmanager put-secret-value \
        --secret-id "ravenhelm/dev/postgres/credentials" \
        --secret-string "{\"username\":\"ravenhelm\",\"password\":\"$NEW_PASSWORD\",\"host\":\"postgres\",\"port\":5432,\"database\":\"ravenhelm\"}"
    
    aws_cmd secretsmanager put-secret-value \
        --secret-id "ravenhelm/dev/database_url" \
        --secret-string "postgresql://ravenhelm:$NEW_PASSWORD@postgres:5432/ravenhelm"
    
    log "✓ PostgreSQL password rotated"
    log ""
    log "Next steps:"
    log "  1. Update docker-compose.yml DATABASE_URL if hardcoded"
    log "  2. Restart dependent services:"
    log "     docker compose restart hlidskjalf langfuse phoenix"
    log "  3. Verify connectivity:"
    log "     docker exec gitlab-sre-postgres psql -U ravenhelm -d ravenhelm -c 'SELECT 1;'"
}

rotate_redis() {
    log "Rotating Redis password..."
    
    NEW_PASSWORD=$(generate_password)
    log "Generated new password: ${NEW_PASSWORD:0:4}...${NEW_PASSWORD: -4}"
    
    log ""
    log "⚠️  Manual steps required:"
    log ""
    log "1. Update config/redis/redis.conf:"
    log "   requirepass $NEW_PASSWORD"
    log "   user default on >$NEW_PASSWORD ~* &* +@all"
    log ""
    log "2. Update docker-compose.yml REDIS_URL references"
    log ""
    
    read -p "Press Enter when config files are updated, or 'skip' to cancel: " confirm
    
    if [ "$confirm" == "skip" ]; then
        log "Skipped Redis rotation"
        return
    fi
    
    # Update Secrets Manager
    log "Updating Secrets Manager..."
    aws_cmd secretsmanager put-secret-value \
        --secret-id "ravenhelm/dev/redis/password" \
        --secret-string "$NEW_PASSWORD"
    
    aws_cmd secretsmanager put-secret-value \
        --secret-id "ravenhelm/dev/redis_url" \
        --secret-string "rediss://:$NEW_PASSWORD@redis:6379/0"
    
    log "✓ Redis secrets updated"
    log ""
    log "Next steps:"
    log "  1. Restart Redis and dependent services:"
    log "     docker compose restart redis hlidskjalf langgraph"
    log "  2. Verify Redis AUTH:"
    log "     docker exec gitlab-sre-redis redis-cli --tls --cacert /run/spire/certs/bundle.pem -a '$NEW_PASSWORD' ping"
}

rotate_zitadel_token() {
    log "Rotating Zitadel service account token..."
    
    log ""
    log "⚠️  Manual steps required:"
    log ""
    log "1. Login to Zitadel Console: https://zitadel.ravenhelm.test"
    log "2. Navigate to: Users > Service Users > Skuld"
    log "3. Go to Personal Access Tokens"
    log "4. Create new token, copy the value"
    log "5. (Optional) Delete the old token"
    log ""
    
    read -p "Enter new Zitadel service account token (or 'skip'): " NEW_TOKEN
    
    if [ "$NEW_TOKEN" == "skip" ] || [ -z "$NEW_TOKEN" ]; then
        log "Skipped Zitadel token rotation"
        return
    fi
    
    # Get current service account ID
    current=$(aws_cmd secretsmanager get-secret-value \
        --secret-id "ravenhelm/dev/zitadel/service_account" \
        --query 'SecretString' --output text 2>/dev/null)
    
    SERVICE_ACCOUNT_ID=$(echo "$current" | jq -r '.id')
    
    # Update secret
    aws_cmd secretsmanager put-secret-value \
        --secret-id "ravenhelm/dev/zitadel/service_account" \
        --secret-string "{\"id\":\"$SERVICE_ACCOUNT_ID\",\"token\":\"$NEW_TOKEN\"}"
    
    log "✓ Zitadel token updated"
    log ""
    log "Next steps:"
    log "  1. Update .env file:"
    log "     ZITADEL_SERVICE_ACCOUNT_TOKEN=$NEW_TOKEN"
    log "  2. Restart services:"
    log "     docker compose restart hlidskjalf"
}

list_secrets() {
    log "Listing all secrets in Secrets Manager..."
    echo ""
    
    aws_cmd secretsmanager list-secrets \
        --query 'SecretList[].{Name:Name,LastChanged:LastChangedDate}' \
        --output table
}

check_expiry() {
    log "Checking secret ages..."
    echo ""
    
    # Get all secrets and their last changed dates
    aws_cmd secretsmanager list-secrets \
        --query 'SecretList[].{Name:Name,LastChanged:LastChangedDate}' \
        --output json | jq -r '.[] | "\(.Name)\t\(.LastChanged)"' | while read line; do
        
        name=$(echo "$line" | cut -f1)
        last_changed=$(echo "$line" | cut -f2)
        
        if [ "$last_changed" != "null" ] && [ -n "$last_changed" ]; then
            # Calculate age in days
            changed_epoch=$(date -d "$last_changed" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S" "${last_changed%%.*}" +%s 2>/dev/null)
            now_epoch=$(date +%s)
            age_days=$(( (now_epoch - changed_epoch) / 86400 ))
            
            # Warn if older than 90 days
            if [ $age_days -gt 90 ]; then
                echo "⚠️  $name - $age_days days old (NEEDS ROTATION)"
            elif [ $age_days -gt 60 ]; then
                echo "⏳ $name - $age_days days old (rotation soon)"
            else
                echo "✓  $name - $age_days days old"
            fi
        else
            echo "❓ $name - age unknown"
        fi
    done
}

# =========================================================================
# Main
# =========================================================================

show_help() {
    cat << EOF
Ravenhelm Secret Rotation Script

Usage: $0 [command]

Commands:
  anthropic    Rotate Anthropic API key
  openai       Rotate OpenAI API key
  deepgram     Rotate Deepgram API key
  elevenlabs   Rotate ElevenLabs API key
  postgres     Rotate PostgreSQL password
  redis        Rotate Redis password
  zitadel      Rotate Zitadel service account token
  list         List all secrets
  check        Check secret ages and rotation status
  help         Show this help

Examples:
  $0 anthropic     # Rotate Anthropic API key
  $0 postgres      # Rotate PostgreSQL password
  $0 check         # Check which secrets need rotation
  $0 list          # List all secrets

Environment Variables:
  AWS_ENDPOINT_URL  LocalStack endpoint (default: http://localhost:4566)
  AWS_REGION        AWS region (default: us-east-1)

See RUNBOOK-010-secret-rotation.md for detailed procedures.
EOF
}

main() {
    local command=${1:-"help"}
    
    case "$command" in
        anthropic|openai|deepgram|elevenlabs)
            rotate_api_key "$command"
            ;;
        postgres|database|db)
            rotate_postgres
            ;;
        redis)
            rotate_redis
            ;;
        zitadel)
            rotate_zitadel_token
            ;;
        list)
            list_secrets
            ;;
        check)
            check_expiry
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "Unknown command: $command. Use 'help' for usage."
            ;;
    esac
}

# Run
main "$@"


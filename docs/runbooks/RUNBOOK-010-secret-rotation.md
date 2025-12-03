# RUNBOOK-010: Secret Rotation

## Overview

This runbook documents procedures for rotating secrets stored in AWS Secrets Manager (LocalStack in dev, AWS in prod). Regular secret rotation is a critical security practice that limits the impact of compromised credentials.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECRET ROTATION FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. Generate New Secret                                        │
│      │                                                          │
│      ▼                                                          │
│   2. Update Secrets Manager                                     │
│      │                                                          │
│      ▼                                                          │
│   3. Update Dependent Service(s)                                │
│      │                                                          │
│      ▼                                                          │
│   4. Verify New Secret Works                                    │
│      │                                                          │
│      ▼                                                          │
│   5. Invalidate Old Secret (if applicable)                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Secret Categories

| Category | Rotation Frequency | Impact | Examples |
|----------|-------------------|--------|----------|
| **Critical** | 90 days | Service outage | Database passwords, Redis AUTH |
| **High** | 90 days | Feature degradation | LLM API keys, Zitadel tokens |
| **Medium** | 180 days | Limited impact | OIDC client secrets |
| **Low** | 365 days | Minimal impact | Feature flags, non-sensitive config |

## Prerequisites

- `awslocal` CLI installed (LocalStack) or `aws` CLI (production)
- Access to the appropriate environment
- Service restart permissions if needed

```bash
# Install awslocal CLI for LocalStack
pip install awscli-local

# Verify connectivity
awslocal secretsmanager list-secrets --query 'SecretList[].Name'
```

## Rotation Procedures

### 1. API Key Rotation (Anthropic, OpenAI, etc.)

**When to Rotate:**
- Every 90 days
- After suspected compromise
- When employee leaves

**Procedure:**

```bash
#!/bin/bash
# rotate-api-key.sh

SECRET_NAME="ravenhelm/dev/anthropic_api_key"
NEW_API_KEY="sk-ant-api03-YOUR_NEW_KEY_HERE"

# Step 1: Update the secret
awslocal secretsmanager put-secret-value \
  --secret-id "$SECRET_NAME" \
  --secret-string "$NEW_API_KEY"

# Step 2: Verify
awslocal secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" \
  --query 'SecretString' \
  --output text

# Step 3: Restart dependent services
docker compose restart hlidskjalf langgraph

# Step 4: Test the new key
curl -s https://hlidskjalf.ravenhelm.test/health
```

**Verification:**
- [ ] Secret updated in Secrets Manager
- [ ] Service restarted successfully
- [ ] Health check passes
- [ ] Test API call works

---

### 2. Database Credential Rotation (PostgreSQL)

**When to Rotate:**
- Every 90 days
- After DBA role change
- After suspected compromise

**Procedure:**

```bash
#!/bin/bash
# rotate-postgres-password.sh

# Step 1: Generate new password
NEW_PASSWORD=$(openssl rand -base64 32 | tr -d '=+/' | head -c 32)
echo "New password: $NEW_PASSWORD"

# Step 2: Update PostgreSQL user (connect to postgres container)
docker exec -it gitlab-sre-postgres psql -U postgres -c \
  "ALTER USER ravenhelm PASSWORD '$NEW_PASSWORD';"

# Step 3: Update Secrets Manager
awslocal secretsmanager put-secret-value \
  --secret-id "ravenhelm/dev/postgres/credentials" \
  --secret-string "{\"username\":\"ravenhelm\",\"password\":\"$NEW_PASSWORD\",\"host\":\"postgres\",\"port\":5432,\"database\":\"ravenhelm\"}"

awslocal secretsmanager put-secret-value \
  --secret-id "ravenhelm/dev/database_url" \
  --secret-string "postgresql://ravenhelm:$NEW_PASSWORD@postgres:5432/ravenhelm"

# Step 4: Restart services that use the database
docker compose restart hlidskjalf langfuse phoenix

# Step 5: Verify connectivity
docker exec -it gitlab-sre-postgres psql -U ravenhelm -d ravenhelm -c "SELECT 1;"
```

**Verification:**
- [ ] PostgreSQL user password changed
- [ ] Secret updated in Secrets Manager
- [ ] Services restarted
- [ ] Database connectivity confirmed

---

### 3. Redis AUTH Password Rotation

**When to Rotate:**
- Every 90 days
- After suspected compromise

**Procedure:**

```bash
#!/bin/bash
# rotate-redis-password.sh

NEW_PASSWORD=$(openssl rand -base64 32 | tr -d '=+/' | head -c 32)
echo "New Redis password: $NEW_PASSWORD"

# Step 1: Update redis.conf
# Edit config/redis/redis.conf:
#   requirepass NEW_PASSWORD
#   user default on >NEW_PASSWORD ~* &* +@all

# Step 2: Update Secrets Manager
awslocal secretsmanager put-secret-value \
  --secret-id "ravenhelm/dev/redis/password" \
  --secret-string "$NEW_PASSWORD"

awslocal secretsmanager put-secret-value \
  --secret-id "ravenhelm/dev/redis_url" \
  --secret-string "rediss://:$NEW_PASSWORD@redis:6379/0"

# Step 3: Update docker-compose.yml REDIS_URL references

# Step 4: Restart Redis and dependent services
docker compose restart redis hlidskjalf langgraph

# Step 5: Verify Redis AUTH
docker exec -it gitlab-sre-redis redis-cli --tls \
  --cacert /run/spire/certs/bundle.pem \
  -a "$NEW_PASSWORD" ping
```

**Verification:**
- [ ] Redis config updated
- [ ] Secret updated in Secrets Manager
- [ ] docker-compose.yml updated
- [ ] Redis and services restarted
- [ ] Redis AUTH working

---

### 4. OIDC Client Secret Rotation

**When to Rotate:**
- Every 180 days
- After suspected compromise

**Procedure:**

```bash
#!/bin/bash
# rotate-oidc-secret.sh
# This requires generating new secrets in Zitadel first

SERVICE="grafana"  # grafana, gitlab, langfuse, etc.
NEW_CLIENT_SECRET="YOUR_NEW_SECRET_FROM_ZITADEL"

# Step 1: Regenerate client secret in Zitadel Console
# Login to https://zitadel.ravenhelm.test
# Navigate to: Projects > Ravenhelm Platform > Applications > [Service]
# Click "Regenerate Secret"

# Step 2: Update Secrets Manager
awslocal secretsmanager get-secret-value \
  --secret-id "ravenhelm/dev/oidc/$SERVICE" \
  --query 'SecretString' | jq -r . | jq ".client_secret = \"$NEW_CLIENT_SECRET\"" > /tmp/secret.json

awslocal secretsmanager put-secret-value \
  --secret-id "ravenhelm/dev/oidc/$SERVICE" \
  --secret-string "$(cat /tmp/secret.json)"

rm /tmp/secret.json

# Step 3: Update docker-compose.yml environment variable

# Step 4: Restart the service
docker compose restart $SERVICE

# Step 5: Verify SSO login works
echo "Test SSO login at https://$SERVICE.ravenhelm.test"
```

**Verification:**
- [ ] New secret generated in Zitadel
- [ ] Secret updated in Secrets Manager
- [ ] docker-compose.yml updated
- [ ] Service restarted
- [ ] SSO login works

---

### 5. Zitadel Service Account Token Rotation

**When to Rotate:**
- Every 90 days
- After employee departure
- After suspected compromise

**Procedure:**

```bash
#!/bin/bash
# rotate-zitadel-token.sh

# Step 1: Generate new Personal Access Token in Zitadel
# Login to https://zitadel.ravenhelm.test
# Navigate to: Users > [Service Account] > Personal Access Tokens
# Create new token, copy value

NEW_TOKEN="YOUR_NEW_TOKEN_HERE"
SERVICE_ACCOUNT_ID="349393442918367258"

# Step 2: Update Secrets Manager
awslocal secretsmanager put-secret-value \
  --secret-id "ravenhelm/dev/zitadel/service_account" \
  --secret-string "{\"id\":\"$SERVICE_ACCOUNT_ID\",\"token\":\"$NEW_TOKEN\"}"

# Step 3: Update .env file
# ZITADEL_SERVICE_ACCOUNT_TOKEN=NEW_TOKEN

# Step 4: Restart services that use the token
docker compose restart hlidskjalf

# Step 5: Verify token works
curl -s -H "Authorization: Bearer $NEW_TOKEN" \
  "https://zitadel.ravenhelm.test/v2/users/me" | jq .
```

**Verification:**
- [ ] New token generated in Zitadel
- [ ] Old token deleted (optional but recommended)
- [ ] Secret updated in Secrets Manager
- [ ] Services restarted
- [ ] API calls with new token succeed

---

## Automation Script

Save this as `scripts/rotate-secrets.sh`:

```bash
#!/bin/bash
# Master secret rotation script
# Usage: ./scripts/rotate-secrets.sh [secret-type]

set -e

SECRET_TYPE=${1:-"help"}

rotate_api_key() {
    local provider=$1
    local secret_name="ravenhelm/dev/${provider}_api_key"
    
    echo "Rotating $provider API key..."
    read -p "Enter new API key: " NEW_KEY
    
    awslocal secretsmanager put-secret-value \
        --secret-id "$secret_name" \
        --secret-string "$NEW_KEY"
    
    echo "Secret updated. Remember to restart dependent services."
}

rotate_database() {
    echo "Rotating PostgreSQL password..."
    
    NEW_PASSWORD=$(openssl rand -base64 32 | tr -d '=+/' | head -c 32)
    
    # Update PostgreSQL
    docker exec -it gitlab-sre-postgres psql -U postgres -c \
        "ALTER USER ravenhelm PASSWORD '$NEW_PASSWORD';"
    
    # Update secrets
    awslocal secretsmanager put-secret-value \
        --secret-id "ravenhelm/dev/postgres/credentials" \
        --secret-string "{\"username\":\"ravenhelm\",\"password\":\"$NEW_PASSWORD\",\"host\":\"postgres\",\"port\":5432,\"database\":\"ravenhelm\"}"
    
    echo "PostgreSQL password rotated. Restart services:"
    echo "  docker compose restart hlidskjalf langfuse phoenix"
}

show_help() {
    cat << EOF
Secret Rotation Script

Usage: $0 [secret-type]

Secret Types:
  anthropic    - Rotate Anthropic API key
  openai       - Rotate OpenAI API key
  postgres     - Rotate PostgreSQL password
  redis        - Rotate Redis password
  list         - List all secrets
  help         - Show this help

Examples:
  $0 anthropic
  $0 postgres
  $0 list
EOF
}

case "$SECRET_TYPE" in
    anthropic|openai|deepgram|elevenlabs)
        rotate_api_key "$SECRET_TYPE"
        ;;
    postgres|database)
        rotate_database
        ;;
    list)
        awslocal secretsmanager list-secrets \
            --query 'SecretList[].{Name:Name,Updated:LastChangedDate}' \
            --output table
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown secret type: $SECRET_TYPE"
        show_help
        exit 1
        ;;
esac
```

## Scheduled Rotation Reminders

Add these to your calendar or ticketing system:

| Secret | Rotation Date | Next Rotation |
|--------|---------------|---------------|
| Anthropic API Key | | +90 days |
| OpenAI API Key | | +90 days |
| PostgreSQL Password | | +90 days |
| Redis Password | | +90 days |
| Zitadel Service Account | | +90 days |
| OIDC Client Secrets | | +180 days |

## Emergency Rotation

If a secret is compromised:

1. **Immediately** rotate the compromised secret
2. **Review** audit logs for unauthorized access
3. **Notify** security team
4. **Document** the incident
5. **Review** access to determine scope of compromise

```bash
# Emergency: Rotate all critical secrets at once
./scripts/rotate-secrets.sh postgres
./scripts/rotate-secrets.sh redis
# Manually regenerate API keys from provider dashboards
```

## Troubleshooting

### Secret Not Found

```bash
# Check secret exists
awslocal secretsmanager describe-secret --secret-id "ravenhelm/dev/SECRET_NAME"

# List all secrets
awslocal secretsmanager list-secrets --query 'SecretList[].Name'
```

### Service Won't Start After Rotation

```bash
# Check service logs
docker compose logs SERVICE_NAME --tail 100

# Verify secret value
awslocal secretsmanager get-secret-value \
  --secret-id "ravenhelm/dev/SECRET_NAME" \
  --query 'SecretString'

# Ensure environment variables are correct in docker-compose.yml
docker compose config | grep -A10 SERVICE_NAME
```

### Database Connection Fails

```bash
# Test connection directly
docker exec -it gitlab-sre-postgres psql -U ravenhelm -d ravenhelm -c "SELECT 1;"

# Check pg_hba.conf allows connections
docker exec -it gitlab-sre-postgres cat /var/lib/postgresql/data/pg_hba.conf
```

## Related Runbooks

- [RUNBOOK-004-spire-management.md](RUNBOOK-004-spire-management.md) - SPIRE certificate rotation
- [RUNBOOK-006-zitadel-sso.md](RUNBOOK-006-zitadel-sso.md) - Zitadel SSO configuration
- [RUNBOOK-005-file-ownership.md](RUNBOOK-005-file-ownership.md) - File permissions

## Revision History

| Date | Author | Changes |
|------|--------|---------|
| 2025-12-03 | Ravenhelm | Initial version |


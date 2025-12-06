#!/bin/bash
# LocalStack initialization script
# Runs automatically when LocalStack is ready
# 
# This script initializes all AWS services needed for the Ravenhelm platform:
# - KMS keys for encryption
# - Secrets Manager for API keys and credentials
# - SSM Parameter Store for configuration
# - S3 buckets for storage
# - SQS queues for messaging
# - SNS topics for notifications

set -e

echo "=== Initializing LocalStack AWS Services ==="
echo "Note: Persistence is enabled - these resources will survive restarts"

# =========================================================================
# KMS - Encryption Keys
# =========================================================================
echo ""
echo "=== Creating KMS Keys ==="

# Create master encryption key
KMS_KEY_ID=$(awslocal kms create-key --description "Ravenhelm master encryption key" --query 'KeyMetadata.KeyId' --output text 2>/dev/null || echo "exists")
if [ "$KMS_KEY_ID" != "exists" ]; then
  awslocal kms create-alias --alias-name alias/ravenhelm-master --target-key-id $KMS_KEY_ID
  echo "KMS master key created: $KMS_KEY_ID"
else
  echo "KMS keys already exist (persistence enabled)"
fi

# =========================================================================
# Secrets Manager - API Keys and Credentials
# =========================================================================
echo ""
echo "=== Creating Secrets ==="

# Helper function to create or update a secret
create_secret() {
  local name=$1
  local value=$2
  local description=$3
  
  if awslocal secretsmanager describe-secret --secret-id "$name" &>/dev/null; then
    echo "  [UPDATE] $name"
    awslocal secretsmanager put-secret-value --secret-id "$name" --secret-string "$value"
  else
    echo "  [CREATE] $name"
    awslocal secretsmanager create-secret \
      --name "$name" \
      --secret-string "$value" \
      --description "$description"
  fi
}

# ---------------------------------------------------------------------------
# LLM Provider API Keys
# ---------------------------------------------------------------------------
echo "Creating LLM provider secrets..."

create_secret "ravenhelm/dev/anthropic_api_key" \
  "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" \
  "Anthropic API key"

create_secret "ravenhelm/dev/openai_api_key" \
  "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" \
  "OpenAI API key"

# Placeholder for future API keys
create_secret "ravenhelm/dev/deepgram_api_key" \
  "dg-dev-placeholder" \
  "Deepgram API key for speech-to-text"

create_secret "ravenhelm/dev/elevenlabs_api_key" \
  "el-dev-placeholder" \
  "ElevenLabs API key for text-to-speech"

# ---------------------------------------------------------------------------
# Twilio Credentials
# ---------------------------------------------------------------------------
echo "Creating Twilio secrets..."

create_secret "ravenhelm/dev/twilio" \
  '{"sid":"AC94d0db92da17f5a5b25dbacc7389dae6","auth_token":"e5ab75afa96d0ef3e217dd64c5603a1e","phone_number":"+17372143330"}' \
  "Twilio credentials (JSON)"

# ---------------------------------------------------------------------------
# Zitadel Service Accounts
# ---------------------------------------------------------------------------
echo "Creating Zitadel secrets..."

create_secret "ravenhelm/dev/zitadel/service_account" \
  '{"id":"349393442918367258","token":"VSv5uVA39rQL5NOjmdBs8n_EERxY_An1koQVp4MFmlLetjldD-jdt5M4nLvuLmLMaCYNlAU"}' \
  "Zitadel automation service account (Skuld)"

create_secret "ravenhelm/dev/zitadel/norns_service_account" \
  '{"id":"349412996360962068","token":"lQb4CPjjJcfQMIZ7lWQk8q12Pj5JGT9kLHLjoJfzvZPXmQlQVwB0vuzB3c8Dc7gttwR1wZk"}' \
  "Norns AI service account"

# MCP / GitLab automation token placeholder
create_secret "ravenhelm/dev/gitlab/mcp_service" \
  '{"token":"SET_GITLAB_PAT","wiki_token":"SET_WIKI_TOKEN","notes":"Replace with real secure tokens"}' \
  "Service account token for MCP GitLab server"

# ---------------------------------------------------------------------------
# OIDC Client Secrets (for SSO)
# ---------------------------------------------------------------------------
echo "Creating OIDC client secrets..."

create_secret "ravenhelm/dev/oidc/grafana" \
  '{"client_id":"349394492199075866","client_secret":"TSVTKij0PMQ1Da8lpS7rwXgXamvBWrCbsB7TaQ7c3PAVW5BOjyjOY6RLGZljGweo"}' \
  "Grafana OIDC credentials"

create_secret "ravenhelm/dev/oidc/gitlab" \
  '{"client_id":"349394492366848026","client_secret":"zQdSdKQlXGnVyt3x0derk5xqFVDNyaRWXnRunMb6XIEubgiu01Fuw0ok2EZAhwHJ"}' \
  "GitLab OIDC credentials"

create_secret "ravenhelm/dev/oidc/vault" \
  '{"client_id":"349394492534620186","client_secret":"yj1rvxk00vewUBXTJ8s7loN6Y8Csglkeelu7yjT4SUywd5Ppsdh5VgWfFaSVT05p"}' \
  "Vault/OpenBao OIDC credentials"

create_secret "ravenhelm/dev/oidc/hlidskjalf" \
  '{"client_id":"349411918341013524","client_secret":"6cdTgn2BCpTqfzPWxBBqSAt1s1XhlpuZyRvyS4XMgon43zbzlch3QufJTQOPFCPp"}' \
  "Hlidskjalf UI OIDC credentials"

create_secret "ravenhelm/dev/oidc/n8n" \
  '{"client_id":"349394492853387290","client_secret":"wovCxkCFzsW6DAjmy3vjyNrs5MXQPnfYaeZvgdwW7CzezhfmtCIindrBhWXmmQjc"}' \
  "n8n OIDC credentials"

create_secret "ravenhelm/dev/oidc/redpanda" \
  '{"client_id":"349394493037936666","client_secret":"yWVoNCfvddTH7wkjPbrPi0emIcZdZmb7LzQIfToT6sCqQyFxc2lDqnOPtzez0w7g"}' \
  "Redpanda Console OIDC credentials"

create_secret "ravenhelm/dev/oidc/langfuse" \
  '{"client_id":"349394493256040474","client_secret":"KPLonNIEV6Ti2ubhsezTc5NzZxA5k6Bo2kpN1n4akcwODe0i0lJ4MZOnfvtQ404p"}' \
  "Langfuse OIDC credentials"

create_secret "ravenhelm/dev/oidc/phoenix" \
  '{"client_id":"349394493440589850","client_secret":"dbmW2LQNempS0dFdIFioIJo70xWoZKOETOOzmA5g7cPidwCnjzHjR5D3LywH3JR0"}' \
  "Phoenix OIDC credentials"

# ---------------------------------------------------------------------------
# NextAuth Secret (for Hlidskjalf UI)
# ---------------------------------------------------------------------------
echo "Creating NextAuth secrets..."

create_secret "ravenhelm/dev/nextauth/secret" \
  "EWJsdn82FjLn8TdhAfEqjehzT1NAETdHlsL953dIhII=" \
  "NextAuth session encryption secret"

# ---------------------------------------------------------------------------
# Database Credentials
# ---------------------------------------------------------------------------
echo "Creating database secrets..."

# Generate a strong password for PostgreSQL
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '=+/' | head -c 32)

create_secret "ravenhelm/dev/postgres/credentials" \
  "{\"username\":\"ravenhelm\",\"password\":\"$POSTGRES_PASSWORD\",\"host\":\"postgres\",\"port\":5432,\"database\":\"ravenhelm\"}" \
  "PostgreSQL credentials"

create_secret "ravenhelm/dev/database_url" \
  "postgresql://ravenhelm:$POSTGRES_PASSWORD@postgres:5432/ravenhelm" \
  "PostgreSQL connection string"

# ---------------------------------------------------------------------------
# Redis Credentials
# ---------------------------------------------------------------------------
echo "Creating Redis secrets..."

# Static password for dev environment (matches config/redis/redis.conf)
# In production, generate dynamically and rotate
REDIS_PASSWORD="ravenhelm-redis-dev-password"

create_secret "ravenhelm/dev/redis/password" \
  "$REDIS_PASSWORD" \
  "Redis AUTH password"

create_secret "ravenhelm/dev/redis_url" \
  "rediss://:$REDIS_PASSWORD@redis:6379/0" \
  "Redis connection string (TLS)"

# ---------------------------------------------------------------------------
# SPIRE Join Token
# ---------------------------------------------------------------------------
echo "Creating SPIRE secrets..."

create_secret "ravenhelm/dev/spire/join_token" \
  "d000d441-8316-4706-a1db-52f6bd22bfe3" \
  "SPIRE agent join token"

echo "Secrets created."

# =========================================================================
# SSM Parameter Store - Configuration
# =========================================================================
echo ""
echo "=== Creating SSM Parameters ==="

# Helper function to create or update a parameter
create_param() {
  local name=$1
  local value=$2
  local description=$3
  
  echo "  $name"
  awslocal ssm put-parameter \
    --name "$name" \
    --value "$value" \
    --type "String" \
    --description "$description" \
    --overwrite 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Environment Configuration
# ---------------------------------------------------------------------------
echo "Creating environment config..."

create_param "/ravenhelm/dev/environment" "dev" "Current environment"
create_param "/ravenhelm/dev/log_level" "DEBUG" "Logging level"
create_param "/ravenhelm/dev/platform/name" "Ravenhelm" "Platform name"
create_param "/ravenhelm/dev/platform/domain" "ravenhelm.test" "Platform domain"

# ---------------------------------------------------------------------------
# LLM Provider Configuration
# ---------------------------------------------------------------------------
echo "Creating LLM config..."

create_param "/ravenhelm/dev/llm/default_provider" "anthropic" "Default LLM provider"
create_param "/ravenhelm/dev/llm/default_model" "claude-sonnet-4-20250514" "Default LLM model"
create_param "/ravenhelm/dev/llm/fallback_provider" "openai" "Fallback LLM provider"
create_param "/ravenhelm/dev/llm/fallback_model" "gpt-4o" "Fallback LLM model"
create_param "/ravenhelm/dev/llm/local_provider" "lmstudio" "Local LLM provider"
create_param "/ravenhelm/dev/llm/local_model" "openai/gpt-oss-20b" "Local LLM model"

# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------
echo "Creating feature flags..."

create_param "/ravenhelm/dev/features/cost_tracking_enabled" "true" "Enable A2A cost tracking"
create_param "/ravenhelm/dev/features/multi_model_routing" "true" "Enable multi-model routing"
create_param "/ravenhelm/dev/features/voice_enabled" "false" "Enable voice features"
create_param "/ravenhelm/dev/features/bifrost_enabled" "false" "Enable Bifrost gateway"

# ---------------------------------------------------------------------------
# Service URLs
# ---------------------------------------------------------------------------
echo "Creating service URLs..."

create_param "/ravenhelm/dev/services/gitlab_url" "https://gitlab.ravenhelm.test" "GitLab URL"
create_param "/ravenhelm/dev/services/registry_url" "https://registry.gitlab.ravenhelm.test" "Container registry URL"
create_param "/ravenhelm/dev/services/zitadel_url" "https://zitadel.ravenhelm.test" "Zitadel IdP URL"
create_param "/ravenhelm/dev/services/grafana_url" "https://grafana.ravenhelm.test" "Grafana URL"
create_param "/ravenhelm/dev/services/langfuse_url" "https://langfuse.ravenhelm.test" "Langfuse URL"
create_param "/ravenhelm/dev/services/hlidskjalf_url" "https://hlidskjalf.ravenhelm.test" "Hlidskjalf UI URL"

# ---------------------------------------------------------------------------
# Zitadel Configuration
# ---------------------------------------------------------------------------
echo "Creating Zitadel config..."

create_param "/ravenhelm/dev/zitadel/issuer" "https://zitadel.ravenhelm.test" "Zitadel issuer URL"
create_param "/ravenhelm/dev/zitadel/project_id" "349394492048015386" "Zitadel project ID"

echo "SSM parameters created."

# =========================================================================
# S3 Buckets
# =========================================================================
echo ""
echo "=== Creating S3 Buckets ==="

create_bucket() {
  local bucket=$1
  if awslocal s3 ls "s3://$bucket" &>/dev/null; then
    echo "  [EXISTS] s3://$bucket"
  else
    echo "  [CREATE] s3://$bucket"
    awslocal s3 mb "s3://$bucket"
  fi
}

# Development artifacts
create_bucket "ravenhelm-artifacts"

# Backup storage
create_bucket "ravenhelm-backups"

# Log archives
create_bucket "ravenhelm-logs"

# Terraform state
create_bucket "ravenhelm-terraform-state"

# Project templates
create_bucket "ravenhelm-project-templates"

# Data lake / analytics
create_bucket "ravenhelm-data"

echo "S3 buckets created."

# =========================================================================
# SQS Queues
# =========================================================================
echo ""
echo "=== Creating SQS Queues ==="

create_queue() {
  local queue=$1
  if awslocal sqs get-queue-url --queue-name "$queue" &>/dev/null; then
    echo "  [EXISTS] $queue"
  else
    echo "  [CREATE] $queue"
    awslocal sqs create-queue --queue-name "$queue"
  fi
}

# Event queues
create_queue "ravenhelm-events"
create_queue "ravenhelm-events-dlq"

# Cost tracking
create_queue "ravenhelm-cost-events"
create_queue "ravenhelm-cost-events-dlq"

# Agent communication
create_queue "ravenhelm-agent-tasks"
create_queue "ravenhelm-agent-tasks-dlq"

echo "SQS queues created."

# =========================================================================
# SNS Topics
# =========================================================================
echo ""
echo "=== Creating SNS Topics ==="

create_topic() {
  local topic=$1
  if awslocal sns list-topics | grep -q "$topic"; then
    echo "  [EXISTS] $topic"
  else
    echo "  [CREATE] $topic"
    awslocal sns create-topic --name "$topic"
  fi
}

# Alert topics
create_topic "ravenhelm-alerts"
create_topic "ravenhelm-cost-alerts"
create_topic "ravenhelm-security-alerts"

# Event topics
create_topic "ravenhelm-agent-events"
create_topic "ravenhelm-deployment-events"

echo "SNS topics created."

# =========================================================================
# Summary
# =========================================================================
echo ""
echo "=========================================="
echo "=== LocalStack Initialization Complete ==="
echo "=========================================="
echo ""
echo "Endpoint: http://localhost:4566"
echo ""
echo "Quick test commands:"
echo "  awslocal secretsmanager list-secrets --query 'SecretList[].Name' --output table"
echo "  awslocal ssm get-parameters-by-path --path /ravenhelm/dev --recursive --query 'Parameters[].Name'"
echo "  awslocal s3 ls"
echo "  awslocal sqs list-queues"
echo "  awslocal sns list-topics"
echo ""
echo "Get a secret:"
echo "  awslocal secretsmanager get-secret-value --secret-id ravenhelm/dev/anthropic_api_key --query SecretString --output text"
echo ""

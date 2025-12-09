# RUNBOOK-026: LLM Configuration System

## Overview

This runbook covers the setup, operation, and troubleshooting of the Hliðskjálf LLM configuration system, which provides centralized, database-backed management of LLM providers and model selection.

## Architecture

### Components

1. **Database Layer**: PostgreSQL tables for providers, models, and configurations
2. **Service Layer**: `LLMProviderService` and `LLMConfigService` for business logic
3. **API Layer**: FastAPI routes for CRUD operations
4. **UI Layer**: React components for configuration management
5. **Integration Layer**: LangChain LLM factory methods

### Interaction Types

The system supports 5 distinct interaction types:

- **reasoning**: Main supervisor thinking (default: gpt-4o @ 0.7)
- **tools**: Tool calling (default: gpt-4o-mini @ 0.1)
- **subagents**: Specialized agents (default: gpt-4o-mini @ 0.5)
- **planning**: TODO generation (default: gpt-4o @ 0.2)
- **embeddings**: Vector embeddings (default: text-embedding-3-small @ 0.0)

### Supported Providers

- **OpenAI**: Automatic model discovery via `/v1/models`
- **Anthropic**: Claude models (hardcoded list)
- **Custom**: Any OpenAI-compatible server (validated on add)

## Prerequisites

- PostgreSQL running on `platform_net`
- LocalStack Secrets Manager for API key storage
- Network access to LLM provider APIs

## Initial Setup

### 1. Database Migration

```bash
# Ensure Postgres is running
docker-compose up -d postgres

# Wait for Postgres to be ready
sleep 5

# Run migration
docker-compose exec postgres psql -U ravenhelm -d ravenhelm_dev \
  -f /docker-entrypoint-initdb.d/002_llm_providers_config.sql
```

**Verification**:
```bash
docker-compose exec postgres psql -U ravenhelm -d ravenhelm_dev -c "\dt llm_*"
```

Expected output:
```
 llm_global_config
 llm_provider_models
 llm_providers
 llm_user_config
```

### 2. Seed Default Configuration

```bash
# Set OpenAI API key (if available)
export OPENAI_API_KEY="sk-..."

# Run seed script
cd hlidskjalf
python -m scripts.seed_llm_config
```

**Expected Output**:
```
✓ Created OpenAI provider: <uuid>
✓ OpenAI provider validated successfully
✓ Found 50+ models: gpt-4o, gpt-4o-mini, ...
✓ Configured reasoning: gpt-4o (temp=0.7)
✓ Configured tools: gpt-4o-mini (temp=0.1)
✓ Configured subagents: gpt-4o-mini (temp=0.5)
✓ Configured planning: gpt-4o (temp=0.2)
✓ Configured embeddings: text-embedding-3-small (temp=0.0)
✓ Seed complete!
```

### 3. Start Hliðskjálf

```bash
docker-compose up -d hlidskjalf
```

### 4. Verify Configuration

```bash
curl http://localhost:8900/api/v1/llm/config
```

## Operations

### Adding a New Provider

#### Via API

**OpenAI Provider**:
```bash
curl -X POST http://localhost:8900/api/v1/llm/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "OpenAI",
    "provider_type": "openai",
    "api_key": "sk-..."
  }'
```

**Anthropic Provider**:
```bash
curl -X POST http://localhost:8900/api/v1/llm/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Anthropic",
    "provider_type": "anthropic",
    "api_key": "sk-ant-..."
  }'
```

**Custom Server** (e.g., vLLM, LM Studio):
```bash
curl -X POST http://localhost:8900/api/v1/llm/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Local vLLM",
    "provider_type": "custom",
    "api_base_url": "http://vllm-server:8000",
    "api_key": "optional-key"
  }'
```

**Verification**:
```bash
# List providers
curl http://localhost:8900/api/v1/llm/providers

# Validate specific provider
curl -X POST http://localhost:8900/api/v1/llm/providers/{provider_id}/validate

# Get available models
curl http://localhost:8900/api/v1/llm/providers/{provider_id}/models
```

### Updating Model Configuration

```bash
curl -X PUT http://localhost:8900/api/v1/llm/config/reasoning \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "<uuid>",
    "model_name": "gpt-4o",
    "temperature": 0.7
  }'
```

**Via UI**:
1. Navigate to https://hlidskjalf.ravenhelm.test:8443
2. Click **"LLM Settings"** button
3. Select **"Model Configuration"** tab
4. Adjust settings for each interaction type
5. Changes save automatically

### Monitoring Configuration

**Get Current Config**:
```bash
curl http://localhost:8900/api/v1/llm/config
```

**Get Human-Readable Summary**:
```bash
curl http://localhost:8900/api/v1/llm/config/summary
```

**Validate All Configs**:
```bash
curl http://localhost:8900/api/v1/llm/config/validate
```

## Troubleshooting

### Provider Validation Fails

**Symptoms**:
- Provider shows as disabled
- `validated_at` is null
- API returns validation errors

**Diagnosis**:
```bash
# Check provider status
curl http://localhost:8900/api/v1/llm/providers/{provider_id}

# Attempt manual validation
curl -X POST http://localhost:8900/api/v1/llm/providers/{provider_id}/validate

# Check Hliðskjálf logs
docker-compose logs hlidskjalf | grep -i "provider\|validation"
```

**Common Causes**:
1. **Invalid API Key**: Verify key is correct and has proper permissions
2. **Network Issues**: Check connectivity to provider API
3. **Custom Server Not Ready**: Ensure `/v1/models` endpoint is accessible
4. **Rate Limiting**: Wait and retry

**Resolution**:
```bash
# Update API key
curl -X PUT http://localhost:8900/api/v1/llm/providers/{provider_id} \
  -H "Content-Type: application/json" \
  -d '{"api_key": "new-key"}'

# Re-validate
curl -X POST http://localhost:8900/api/v1/llm/providers/{provider_id}/validate
```

### Configuration Not Loading

**Symptoms**:
- Norns fails to start
- LLM invocations fail
- Errors about missing configuration

**Diagnosis**:
```bash
# Check database connectivity
docker-compose exec postgres psql -U ravenhelm -d ravenhelm_dev \
  -c "SELECT * FROM llm_global_config;"

# Check service logs
docker-compose logs hlidskjalf | grep -i "llm\|config"

# Verify API endpoint
curl http://localhost:8900/api/v1/llm/config
```

**Common Causes**:
1. **Migration Not Run**: Tables don't exist
2. **Seed Not Run**: No default configuration
3. **Database Connection Issues**: Can't reach Postgres
4. **Service Initialization Error**: Check logs

**Resolution**:
```bash
# Re-run migration
docker-compose exec postgres psql -U ravenhelm -d ravenhelm_dev \
  -f /docker-entrypoint-initdb.d/002_llm_providers_config.sql

# Re-run seed
cd hlidskjalf && python -m scripts.seed_llm_config

# Restart Hliðskjálf
docker-compose restart hlidskjalf
```

### Models Not Available

**Symptoms**:
- Provider shows 0 models
- UI shows empty model dropdown
- Can't select desired model

**Diagnosis**:
```bash
# Check provider models
curl http://localhost:8900/api/v1/llm/providers/{provider_id}/models

# Check provider validation status
curl http://localhost:8900/api/v1/llm/providers/{provider_id}
```

**Common Causes**:
1. **Provider Not Validated**: Run validation first
2. **API Endpoint Unreachable**: Check network/firewall
3. **Custom Server Not Exposing Models**: Verify `/v1/models` works

**Resolution**:
```bash
# Validate provider (fetches models)
curl -X POST http://localhost:8900/api/v1/llm/providers/{provider_id}/validate

# For custom servers, test endpoint directly
curl http://custom-server:8000/v1/models
```

### API Key Decryption Fails

**Symptoms**:
- Provider validation fails with auth errors
- Logs show "Failed to decrypt API key"
- LocalStack errors

**Diagnosis**:
```bash
# Check LocalStack is running
docker-compose ps localstack

# Check secrets exist
aws --endpoint-url=http://localhost:4566 \
  secretsmanager list-secrets

# Check specific secret
aws --endpoint-url=http://localhost:4566 \
  secretsmanager get-secret-value \
  --secret-id ravenhelm/dev/llm/OpenAI
```

**Resolution**:
```bash
# Restart LocalStack
docker-compose restart localstack

# Re-add provider (will recreate secret)
curl -X POST http://localhost:8900/api/v1/llm/providers \
  -H "Content-Type: application/json" \
  -d '{"name": "OpenAI", "provider_type": "openai", "api_key": "sk-..."}'
```

### UI Not Showing Configuration

**Symptoms**:
- LLM Settings panel is blank
- Loading spinner never stops
- Console shows API errors

**Diagnosis**:
```bash
# Check frontend API routes
curl http://localhost:3000/api/llm/config
curl http://localhost:3000/api/llm/providers

# Check backend is accessible
curl http://localhost:8900/api/v1/llm/config

# Check browser console for errors
# (Open DevTools → Console)
```

**Resolution**:
```bash
# Verify BACKEND_URL is set correctly
docker-compose exec hlidskjalf-ui env | grep BACKEND

# Restart UI
docker-compose restart hlidskjalf-ui

# Clear browser cache and reload
```

## Maintenance

### Rotating API Keys

```bash
# Update provider with new key
curl -X PUT http://localhost:8900/api/v1/llm/providers/{provider_id} \
  -H "Content-Type: application/json" \
  -d '{"api_key": "new-key"}'

# Validate with new key
curl -X POST http://localhost:8900/api/v1/llm/providers/{provider_id}/validate
```

### Backing Up Configuration

```bash
# Export configuration
docker-compose exec postgres pg_dump -U ravenhelm -d ravenhelm_dev \
  -t llm_providers -t llm_provider_models \
  -t llm_global_config -t llm_user_config \
  > llm_config_backup.sql

# Restore configuration
docker-compose exec -T postgres psql -U ravenhelm -d ravenhelm_dev \
  < llm_config_backup.sql
```

### Monitoring Usage

```bash
# Check Prometheus metrics
curl http://localhost:8900/metrics | grep llm

# Check Grafana dashboard
# Navigate to: https://grafana.observe.ravenhelm.test:8443
# Dashboard: "Hliðskjálf - LLM Usage"
```

## Security Considerations

1. **API Keys**: Stored encrypted in LocalStack Secrets Manager
2. **Network**: Providers accessed via HTTPS (OpenAI, Anthropic)
3. **Custom Servers**: Should be on `platform_net` or behind Traefik
4. **User Overrides**: Optional per-user configs (not yet implemented)

## Related Documentation

- [LLM Configuration Guide](/docs/LLM_CONFIGURATION_GUIDE.md)
- [RUNBOOK-024: Add Shared Service](/docs/runbooks/RUNBOOK-024-add-shared-service.md)
- [Architecture: Cognitive Components](/docs/architecture/cognitive-architecture.md)

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2025-12-06 | Norns | Initial creation - database-backed LLM config system |


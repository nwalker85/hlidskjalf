# LLM Configuration System Guide

## Overview

The Hliðskjálf platform uses a database-backed LLM configuration system that supports multiple providers (OpenAI, Anthropic, custom OpenAI-compatible servers) with granular model selection per interaction type.

## Architecture

### Interaction Types

The system provides 5 distinct interaction types, each optimized for different use cases:

| Interaction Type | Purpose | Default Model | Default Temp |
|-----------------|---------|---------------|--------------|
| **Reasoning** | Main supervisor thinking and decision making | gpt-4o | 0.7 |
| **Tools** | Tool calling and result parsing | gpt-4o-mini | 0.1 |
| **Subagents** | Specialized agent tasks | gpt-4o-mini | 0.5 |
| **Planning** | TODO generation and planning | gpt-4o | 0.2 |
| **Embeddings** | Vector embeddings for RAG | text-embedding-3-small | 0.0 |

### Supported Providers

1. **OpenAI** - Automatic model discovery via API
2. **Anthropic** - Claude models (hardcoded list)
3. **Custom** - Any OpenAI-compatible server (validated on add)

## Setup

### 1. Database Migration

Run the LLM configuration migration:

```bash
# From project root
psql $DATABASE_URL < hlidskjalf/migrations/versions/002_llm_providers_config.sql
```

### 2. Seed Default Configuration

```bash
# Set OpenAI API key (optional - can be added via UI)
export OPENAI_API_KEY="sk-..."

# Run seed script
cd hlidskjalf
python -m scripts.seed_llm_config
```

This will:
- Create default OpenAI provider
- Configure sensible defaults for all interaction types
- Validate the setup

### 3. Access the UI

1. Navigate to Hliðskjálf dashboard
2. Click **"LLM Settings"** button in the header
3. Review and adjust configuration as needed

## Using the System

### Via UI

#### Configure Models

1. Open **LLM Settings** from dashboard
2. Select **"Model Configuration"** tab
3. For each interaction type:
   - Choose provider
   - Select model
   - Adjust temperature slider
4. Changes are saved automatically

#### Manage Providers

1. Open **LLM Settings**
2. Select **"Providers"** tab
3. View provider status and models
4. Add new providers via API (see below)

### Via API

#### List Providers

```bash
curl http://localhost:8900/api/v1/llm/providers
```

#### Add OpenAI Provider

```bash
curl -X POST http://localhost:8900/api/v1/llm/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "OpenAI",
    "provider_type": "openai",
    "api_key": "sk-..."
  }'
```

#### Add Anthropic Provider

```bash
curl -X POST http://localhost:8900/api/v1/llm/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Anthropic",
    "provider_type": "anthropic",
    "api_key": "sk-ant-..."
  }'
```

#### Add Custom Server

```bash
curl -X POST http://localhost:8900/api/v1/llm/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Local LLM",
    "provider_type": "custom",
    "api_base_url": "http://localhost:8000",
    "api_key": "optional-key"
  }'
```

The custom server will be validated by checking the `/v1/models` endpoint.

#### Get Global Configuration

```bash
curl http://localhost:8900/api/v1/llm/config
```

#### Update Interaction Configuration

```bash
curl -X PUT http://localhost:8900/api/v1/llm/config/reasoning \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "uuid-here",
    "model_name": "gpt-4o",
    "temperature": 0.7
  }'
```

## Database Schema

### Tables

- **llm_providers**: Provider configurations (OpenAI, Anthropic, custom)
- **llm_provider_models**: Models available per provider
- **llm_global_config**: Default configuration per interaction type
- **llm_user_config**: User-specific overrides (optional)

### API Key Storage

API keys are encrypted and stored in LocalStack Secrets Manager at:
- `ravenhelm/dev/llm/{provider_name}`

Only the secret path is stored in the database.

## Migration from Old System

The old system used environment variables:
- `OLLAMA_URL`, `OLLAMA_CHAT_MODEL` - Removed
- `LMSTUDIO_URL`, `LMSTUDIO_MODEL` - Removed
- `HUGGINGFACE_TGI_URL` - Removed

These have been replaced with database configuration.

### Fallback Behavior

If database configuration fails to load, the system falls back to:
- `OPENAI_API_KEY` environment variable
- Default models: gpt-4o (reasoning), gpt-4o-mini (tools/subagents)

## Custom Server Requirements

Custom servers must be OpenAI API compatible and provide:

1. **Model List Endpoint**: `GET /v1/models`
   ```json
   {
     "data": [
       {"id": "model-name", ...}
     ]
   }
   ```

2. **Chat Completions**: `POST /v1/chat/completions`
3. **Embeddings** (optional): `POST /v1/embeddings`

Examples of compatible servers:
- vLLM
- LM Studio
- LocalAI
- Text Generation Inference (TGI)
- Ollama (with OpenAI compatibility mode)

## Troubleshooting

### Provider Validation Failed

If custom server validation fails:
1. Ensure server is running and accessible
2. Check `/v1/models` endpoint returns valid JSON
3. Verify API key if required
4. Check network connectivity

### Configuration Not Loading

If models aren't being used:
1. Verify database migration ran successfully
2. Check seed script completed without errors
3. Validate configuration via API: `GET /api/v1/llm/config`
4. Check logs for connection errors

### API Key Issues

If authentication fails:
1. Verify API key is correct
2. Check LocalStack Secrets Manager is running
3. Validate secret path in database matches stored secret
4. Test provider via validation endpoint

## Best Practices

1. **Use gpt-4o for reasoning** - Better quality for main supervisor
2. **Use gpt-4o-mini for tools** - Fast and cheap for tool calling
3. **Set low temperature for tools** - More deterministic outputs
4. **Set higher temperature for reasoning** - More creative solutions
5. **Use embeddings model for RAG** - Dedicated model for vector search
6. **Validate custom servers** - Always test before deploying
7. **Monitor costs** - Track usage per interaction type
8. **Use user overrides sparingly** - Global config is usually sufficient

## API Reference

See `/api/v1/docs` for complete API documentation with interactive Swagger UI.

Key endpoints:
- `GET /api/v1/llm/providers` - List providers
- `POST /api/v1/llm/providers` - Add provider
- `POST /api/v1/llm/providers/{id}/validate` - Validate provider
- `GET /api/v1/llm/providers/{id}/models` - Get models
- `GET /api/v1/llm/config` - Get global config
- `PUT /api/v1/llm/config/{interaction_type}` - Update config
- `GET /api/v1/llm/config/summary` - Get readable summary
- `GET /api/v1/llm/config/validate` - Validate all configs

## Support

For issues or questions:
1. Check logs: `docker logs hlidskjalf`
2. Validate configuration via API
3. Review this guide
4. Check `docs/LESSONS_LEARNED.md` for known issues


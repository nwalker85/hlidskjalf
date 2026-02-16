# LLM Configuration System

The Hliðskjálf platform uses a database-backed LLM configuration system that allows dynamic model selection for different interaction types without code changes or service restarts.

## Overview

The system supports:
- **Multiple providers**: OpenAI, Anthropic, and custom OpenAI-compatible servers
- **Granular configuration**: Different models for reasoning, tools, subagents, planning, and embeddings
- **Persistent storage**: Configuration stored in PostgreSQL
- **Secure secrets**: API keys encrypted in LocalStack Secrets Manager
- **UI management**: Web-based configuration interface
- **API-first**: Full REST API for programmatic control

## Architecture

### Database Schema

Four main tables:

1. **`llm_providers`**: Stores provider configurations
   - OpenAI, Anthropic, or custom server details
   - API key stored as secret path (not plaintext)
   - Enabled/disabled flag

2. **`llm_provider_models`**: Models available per provider
   - Auto-populated from provider APIs
   - Capabilities (tools, embeddings)
   - Cost information
   - Context window size

3. **`llm_global_config`**: Default model per interaction type
   - One row per interaction type
   - References provider + model
   - Temperature and token settings

4. **`llm_user_config`**: User-specific overrides (optional)
   - Per-user customization
   - Falls back to global config

### Interaction Types

The system supports 5 granular interaction types:

| Type | Purpose | Default Model | Default Temp |
|------|---------|---------------|--------------|
| **reasoning** | Main supervisor thinking and decision making | gpt-4o | 0.7 |
| **tools** | Tool calling and result parsing | gpt-4o-mini | 0.1 |
| **subagents** | Specialized agent tasks | gpt-4o-mini | 0.5 |
| **planning** | TODO generation and planning | gpt-4o | 0.2 |
| **embeddings** | Vector embeddings for RAG | text-embedding-3-small | 0.0 |

## Setup

### 1. Run Migration

```bash
# Apply the database schema
psql -U ravenhelm -d hlidskjalf -f hlidskjalf/migrations/versions/002_llm_providers_config.sql
```

### 2. Seed Default Configuration

```bash
# Set OpenAI API key (optional - can be added via UI)
export OPENAI_API_KEY="sk-..."

# Run seed script
python -m hlidskjalf.scripts.seed_llm_config
```

This creates:
- OpenAI provider
- Default models for all 5 interaction types
- Sensible temperature defaults

### 3. Access Configuration UI

1. Navigate to Hliðskjálf dashboard
2. Click **"LLM Settings"** button in header
3. Configure providers and models

## Usage

### Via UI

**Main Dashboard → LLM Settings Button**

**Configuration Tab**:
- Select provider and model for each interaction type
- Adjust temperature sliders
- Changes apply immediately

**Providers Tab**:
- View configured providers
- See enabled/disabled status
- (Add/edit functionality via API)

### Via API

#### List Providers

```bash
GET /api/v1/llm/providers
```

```json
[
  {
    "id": "uuid",
    "name": "OpenAI",
    "provider_type": "openai",
    "enabled": true,
    "validated_at": "2024-01-01T00:00:00Z"
  }
]
```

#### Add Provider

**OpenAI:**
```bash
POST /api/v1/llm/providers
Content-Type: application/json

{
  "name": "OpenAI",
  "provider_type": "openai",
  "api_key": "sk-..."
}
```

**Custom Server:**
```bash
POST /api/v1/llm/providers
Content-Type: application/json

{
  "name": "LM Studio",
  "provider_type": "custom",
  "api_base_url": "http://localhost:1234/v1",
  "api_key": "optional"
}
```

#### Validate Provider

```bash
POST /api/v1/llm/providers/{id}/validate
```

For custom servers, validates `/v1/models` endpoint.

#### Get Available Models

```bash
GET /api/v1/llm/providers/{id}/models
```

Auto-fetches from provider API if not cached.

#### Get Global Configuration

```bash
GET /api/v1/llm/config
```

Returns configuration for all 5 interaction types.

#### Update Interaction Configuration

```bash
PUT /api/v1/llm/config/reasoning
Content-Type: application/json

{
  "provider_id": "uuid",
  "model_name": "gpt-4o",
  "temperature": 0.7,
  "max_tokens": null
}
```

## Provider Support

### OpenAI

- **Auto-discovery**: Models fetched from API
- **Supported**: GPT-4o, GPT-4o-mini, GPT-3.5-turbo, embeddings
- **Features**: Tool calling, streaming, embeddings

### Anthropic

- **Hardcoded models**: API doesn't provide model list
- **Supported**: Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus
- **Features**: Tool calling, long context (200K tokens)

### Custom OpenAI-Compatible Servers

- **Examples**: LM Studio, Ollama with OpenAI adapter, vLLM, text-generation-inference
- **Validation**: Must have `/v1/models` endpoint
- **Discovery**: Models auto-fetched from server
- **Requirements**: OpenAI-compatible API format

## Security

### API Key Storage

API keys are **never** stored in plaintext:

1. Key submitted via API/UI
2. Stored in LocalStack Secrets Manager
3. Path saved in database (e.g., `ravenhelm/dev/llm/openai`)
4. Retrieved at runtime when creating LLM instances

### Secrets Manager Integration

```python
# Keys stored at
ravenhelm/dev/llm/{provider_name_lowercase}

# Example paths:
ravenhelm/dev/llm/openai
ravenhelm/dev/llm/anthropic
ravenhelm/dev/llm/lm_studio
```

## Code Integration

### Creating LLM Instances

The Norns agent automatically uses configured models:

```python
# In agent.py
llm = create_llm()  # Uses database config for reasoning

# In specialized_agents.py  
llm = get_agent_llm()  # Uses config for tools/subagents

# In planner.py
llm = await _get_planning_llm()  # Uses config for planning
```

### Configuration Service

For manual LLM creation:

```python
from src.services.llm_config import LLMConfigService
from src.models.llm_config import InteractionType

async with async_session() as session:
    service = LLMConfigService(session)
    
    # Get LLM for specific purpose
    llm = await service.get_llm_for_interaction(
        InteractionType.REASONING
    )
    
    # Get embeddings model
    embeddings = await service.get_embeddings_model()
    
    # Get LLM with tools bound
    llm_with_tools = await service.get_llm_with_tools(
        InteractionType.TOOLS,
        tools=[...]
    )
```

## Fallback Behavior

If database configuration fails, the system falls back to:

1. Check `OPENAI_API_KEY` environment variable
2. Use sensible defaults:
   - Reasoning: gpt-4o
   - Tools/Subagents: gpt-4o-mini
   - Planning: gpt-4o
   - Embeddings: text-embedding-3-small

## Troubleshooting

### "No LLM configuration available"

**Solution**: Run seed script or add provider via API

```bash
python -m hlidskjalf.scripts.seed_llm_config
```

### "Provider validation failed"

For custom servers:
- Ensure server is running
- Check `/v1/models` endpoint returns valid JSON
- Verify API key if required

### "Model not found for provider"

**Solution**: Manually add model

```bash
POST /api/v1/llm/providers/{id}/models
Content-Type: application/json

{
  "model_name": "my-model",
  "supports_tools": true,
  "supports_embeddings": false,
  "context_window": 4096
}
```

### Models not appearing in UI

**Solution**: Refresh models from provider

```bash
GET /api/v1/llm/providers/{id}/models
```

This will fetch fresh model list from provider API.

## Migration from Old System

### Old (Ollama/LM Studio in env vars):

```bash
# .env
OLLAMA_URL=http://ollama:11434
OLLAMA_CHAT_MODEL=mistral-nemo:latest
LLM_PROVIDER=ollama
```

### New (Database config):

1. Remove old env vars (optional - still work as fallback)
2. Run migration + seed script
3. Configure via UI or API
4. System automatically uses database config

## Best Practices

1. **Use reasoning model for complex thinking**: gpt-4o, claude-3.5-sonnet
2. **Use tools model for fast parsing**: gpt-4o-mini, claude-3.5-haiku
3. **Set temperature appropriately**:
   - Low (0.0-0.2) for deterministic tasks
   - Medium (0.5-0.7) for creative tasks
   - High (0.8-1.0) for very creative tasks
4. **Monitor costs**: Check model pricing in `llm_provider_models` table
5. **Validate custom servers**: Always run validation after adding
6. **Keep API keys in Secrets Manager**: Never commit to git

## API Reference

Full OpenAPI documentation available at:

```
http://hlidskjalf:8900/docs#/LLM%20Configuration
```

## Files Reference

### Backend

- **Migration**: [`hlidskjalf/migrations/versions/002_llm_providers_config.sql`]
- **Models**: [`hlidskjalf/src/models/llm_config.py`]
- **Provider Service**: [`hlidskjalf/src/services/llm_providers.py`]
- **Config Service**: [`hlidskjalf/src/services/llm_config.py`]
- **API Routes**: [`hlidskjalf/src/api/llm_config.py`]
- **Seed Script**: [`hlidskjalf/scripts/seed_llm_config.py`]

### Frontend

- **Settings Panel**: [`hlidskjalf/ui/src/components/llm-settings/LLMSettingsPanel.tsx`]
- **Dashboard**: [`hlidskjalf/ui/src/app/page.tsx`]
- **API Proxies**: [`hlidskjalf/ui/src/app/api/llm/`]

### Agent Integration

- **Main Agent**: [`hlidskjalf/src/norns/agent.py`]
- **Specialized Agents**: [`hlidskjalf/src/norns/specialized_agents.py`]
- **Planner**: [`hlidskjalf/src/norns/planner.py`]


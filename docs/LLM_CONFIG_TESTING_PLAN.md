# LLM Configuration System - Testing Plan

## Overview

This document outlines the testing strategy for the new database-backed LLM configuration system. It covers unit tests, integration tests, and manual verification procedures.

## Test Environment Setup

### Prerequisites

1. PostgreSQL running on `platform_net`
2. LocalStack Secrets Manager operational
3. Hliðskjálf service running
4. OpenAI API key (for provider validation tests)

### Setup Steps

```bash
# 1. Ensure platform is running
cd /Users/nwalker/Development/hlidskjalf
docker-compose up -d postgres localstack

# 2. Run database migration
docker-compose exec postgres psql -U ravenhelm -d ravenhelm_dev \
  -f /docker-entrypoint-initdb.d/002_llm_providers_config.sql

# 3. Set OpenAI API key
export OPENAI_API_KEY="sk-..."

# 4. Run seed script
cd hlidskjalf
python -m scripts.seed_llm_config

# 5. Start Hliðskjálf
docker-compose up -d hlidskjalf hlidskjalf-ui
```

## Test Categories

### 1. Database Layer Tests

#### 1.1 Schema Validation

**Test**: Verify all tables exist with correct structure

```bash
docker-compose exec postgres psql -U ravenhelm -d ravenhelm_dev -c "
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name LIKE 'llm_%' 
ORDER BY table_name, ordinal_position;
"
```

**Expected**: 4 tables with correct columns:
- `llm_providers` (9 columns)
- `llm_provider_models` (7 columns)
- `llm_global_config` (5 columns)
- `llm_user_config` (6 columns)

#### 1.2 Seed Data Validation

**Test**: Verify default configuration exists

```bash
docker-compose exec postgres psql -U ravenhelm -d ravenhelm_dev -c "
SELECT 
  interaction_type,
  p.name as provider_name,
  gc.model_name,
  gc.temperature
FROM llm_global_config gc
JOIN llm_providers p ON gc.provider_id = p.id
ORDER BY interaction_type;
"
```

**Expected**: 5 rows with:
- reasoning → OpenAI/gpt-4o/0.7
- tools → OpenAI/gpt-4o-mini/0.1
- subagents → OpenAI/gpt-4o-mini/0.5
- planning → OpenAI/gpt-4o/0.2
- embeddings → OpenAI/text-embedding-3-small/0.0

### 2. Service Layer Tests

#### 2.1 LLMProviderService Tests

**Test 2.1.1**: Add OpenAI provider

```python
# In hlidskjalf/tests/test_llm_providers.py
import pytest
from src.services.llm_providers import LLMProviderService
from src.models.llm_config import LLMProviderType

@pytest.mark.asyncio
async def test_add_openai_provider(db_session):
    service = LLMProviderService(db_session)
    
    provider = await service.add_provider(
        name="Test OpenAI",
        provider_type=LLMProviderType.OPENAI,
        api_key="sk-test123"
    )
    
    assert provider.id is not None
    assert provider.name == "Test OpenAI"
    assert provider.provider_type == LLMProviderType.OPENAI
    assert provider.api_key_encrypted is not None
```

**Test 2.1.2**: Validate provider

```python
@pytest.mark.asyncio
async def test_validate_provider(db_session, openai_provider_id):
    service = LLMProviderService(db_session)
    
    is_valid = await service.validate_provider(openai_provider_id)
    
    assert is_valid is True
```

**Test 2.1.3**: Fetch available models

```python
@pytest.mark.asyncio
async def test_get_available_models(db_session, openai_provider_id):
    service = LLMProviderService(db_session)
    
    models = await service.get_available_models(openai_provider_id)
    
    assert len(models) > 0
    assert "gpt-4o" in models
    assert "gpt-4o-mini" in models
```

#### 2.2 LLMConfigService Tests

**Test 2.2.1**: Get global configuration

```python
@pytest.mark.asyncio
async def test_get_global_config(db_session):
    service = LLMConfigService(db_session)
    
    config = await service.get_global_config()
    
    assert LLMInteractionType.REASONING in config
    assert LLMInteractionType.TOOLS in config
    assert config[LLMInteractionType.REASONING].model_name == "gpt-4o"
```

**Test 2.2.2**: Update interaction config

```python
@pytest.mark.asyncio
async def test_update_interaction_config(db_session, openai_provider_id):
    service = LLMConfigService(db_session)
    
    updated = await service.update_interaction_config(
        interaction_type=LLMInteractionType.REASONING,
        provider_id=openai_provider_id,
        model_name="gpt-4o-mini",
        temperature=0.5
    )
    
    assert updated.model_name == "gpt-4o-mini"
    assert updated.temperature == 0.5
```

**Test 2.2.3**: Get LLM for interaction

```python
@pytest.mark.asyncio
async def test_get_llm_for_interaction(db_session):
    service = LLMConfigService(db_session)
    
    llm = await service.get_llm_for_interaction(
        LLMInteractionType.REASONING,
        bind_tools=True
    )
    
    assert llm is not None
    assert isinstance(llm, ChatOpenAI)
```

**Test 2.2.4**: Get embeddings model

```python
@pytest.mark.asyncio
async def test_get_embeddings_model(db_session):
    service = LLMConfigService(db_session)
    
    embeddings = await service.get_embeddings_model()
    
    assert embeddings is not None
    assert isinstance(embeddings, OpenAIEmbeddings)
```

### 3. API Layer Tests

#### 3.1 Provider Endpoints

**Test 3.1.1**: List providers

```bash
curl -s http://localhost:8900/api/v1/llm/providers | jq
```

**Expected**:
```json
{
  "providers": [
    {
      "id": "uuid",
      "name": "OpenAI",
      "provider_type": "openai",
      "enabled": true,
      "validated_at": "2025-12-06T...",
      "models": ["gpt-4o", "gpt-4o-mini", ...]
    }
  ]
}
```

**Test 3.1.2**: Add provider

```bash
curl -X POST http://localhost:8900/api/v1/llm/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Provider",
    "provider_type": "openai",
    "api_key": "sk-test"
  }' | jq
```

**Expected**: 201 Created with provider object

**Test 3.1.3**: Validate provider

```bash
PROVIDER_ID="uuid-from-above"
curl -X POST http://localhost:8900/api/v1/llm/providers/$PROVIDER_ID/validate | jq
```

**Expected**: `{"valid": true}` or `{"valid": false, "error": "..."}`

**Test 3.1.4**: Get provider models

```bash
curl http://localhost:8900/api/v1/llm/providers/$PROVIDER_ID/models | jq
```

**Expected**: `{"models": ["model1", "model2", ...]}`

#### 3.2 Configuration Endpoints

**Test 3.2.1**: Get global config

```bash
curl http://localhost:8900/api/v1/llm/config | jq
```

**Expected**:
```json
{
  "config": {
    "reasoning": {
      "provider_id": "uuid",
      "provider_name": "OpenAI",
      "model_name": "gpt-4o",
      "temperature": 0.7
    },
    ...
  }
}
```

**Test 3.2.2**: Update interaction config

```bash
curl -X PUT http://localhost:8900/api/v1/llm/config/reasoning \
  -H "Content-Type: application/json" \
  -d '{
    "provider_id": "uuid",
    "model_name": "gpt-4o-mini",
    "temperature": 0.5
  }' | jq
```

**Expected**: Updated config object

**Test 3.2.3**: Get config summary

```bash
curl http://localhost:8900/api/v1/llm/config/summary | jq
```

**Expected**: Human-readable summary

**Test 3.2.4**: Validate all configs

```bash
curl http://localhost:8900/api/v1/llm/config/validate | jq
```

**Expected**: `{"valid": true}` or validation errors

### 4. Integration Tests

#### 4.1 Norns Agent Integration

**Test 4.1.1**: Norns uses configured model

```python
# In hlidskjalf/tests/test_norns_integration.py
@pytest.mark.asyncio
async def test_norns_uses_configured_model(db_session):
    # Set up config
    config_service = LLMConfigService(db_session)
    await config_service.update_interaction_config(
        LLMInteractionType.REASONING,
        provider_id=openai_provider_id,
        model_name="gpt-4o-mini",
        temperature=0.5
    )
    
    # Invoke Norns
    from src.norns.agent import norns_node
    state = {"messages": [HumanMessage(content="Hello")]}
    result = await norns_node(state)
    
    # Verify response
    assert result["messages"][-1].content is not None
```

#### 4.2 Subagent Integration

**Test 4.2.1**: Subagents use configured model

```python
@pytest.mark.asyncio
async def test_subagent_uses_configured_model(db_session):
    from src.norns.specialized_agents import create_file_management_agent
    
    agent = await create_file_management_agent()
    
    # Verify agent is using correct model
    # (implementation depends on agent structure)
```

#### 4.3 Planner Integration

**Test 4.3.1**: Planner uses configured model

```python
@pytest.mark.asyncio
async def test_planner_uses_configured_model(db_session):
    from src.norns.planner import generate_todo_plan
    
    plan = await generate_todo_plan(
        task="Test task",
        context={"test": "data"}
    )
    
    assert plan is not None
    assert len(plan) > 0
```

#### 4.4 Muninn Integration

**Test 4.4.1**: Muninn uses configured embeddings

```python
@pytest.mark.asyncio
async def test_muninn_uses_configured_embeddings(db_session):
    from src.memory.muninn.store import MuninnStore
    
    store = MuninnStore()
    
    # Store a memory
    await store.store_memory(
        content="Test memory",
        domain="test"
    )
    
    # Query it back
    results = await store.query_memory("Test", domain="test")
    
    assert len(results) > 0
```

### 5. UI Tests

#### 5.1 LLM Settings Panel

**Test 5.1.1**: Panel opens and loads data

1. Navigate to https://hlidskjalf.ravenhelm.test:8443
2. Click "LLM Settings" button
3. Verify panel opens
4. Verify providers load
5. Verify config loads

**Expected**: No loading errors, data displays correctly

**Test 5.1.2**: Switch model for interaction type

1. Open LLM Settings
2. Select "Model Configuration" tab
3. For "Reasoning", change model from gpt-4o to gpt-4o-mini
4. Wait for save indicator
5. Refresh page and reopen settings

**Expected**: Model change persists

**Test 5.1.3**: Adjust temperature

1. Open LLM Settings
2. Select "Model Configuration" tab
3. For "Tools", drag temperature slider to 0.3
4. Wait for save indicator
5. Verify via API: `curl http://localhost:8900/api/v1/llm/config | jq '.config.tools.temperature'`

**Expected**: Temperature updates to 0.3

**Test 5.1.4**: View providers

1. Open LLM Settings
2. Select "Providers" tab
3. Verify OpenAI provider shows
4. Verify models list displays
5. Verify validation timestamp shows

**Expected**: Provider information displays correctly

### 6. Error Handling Tests

#### 6.1 Invalid API Key

**Test**: Add provider with invalid API key

```bash
curl -X POST http://localhost:8900/api/v1/llm/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Invalid OpenAI",
    "provider_type": "openai",
    "api_key": "sk-invalid"
  }'
```

**Expected**: Provider created but validation fails

#### 6.2 Unreachable Custom Server

**Test**: Add custom server that doesn't exist

```bash
curl -X POST http://localhost:8900/api/v1/llm/providers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Unreachable Server",
    "provider_type": "custom",
    "api_base_url": "http://nonexistent:8000"
  }'
```

**Expected**: Provider created but validation fails with network error

#### 6.3 Missing Configuration

**Test**: Request LLM for unconfigured interaction type

```python
@pytest.mark.asyncio
async def test_missing_config_falls_back(db_session):
    # Delete all configs
    await db_session.execute("DELETE FROM llm_global_config")
    await db_session.commit()
    
    service = LLMConfigService(db_session)
    
    # Should fall back to defaults
    llm = await service.get_llm_for_interaction(LLMInteractionType.REASONING)
    
    assert llm is not None
```

### 7. Performance Tests

#### 7.1 Configuration Load Time

**Test**: Measure time to load global config

```python
import time

@pytest.mark.asyncio
async def test_config_load_performance(db_session):
    service = LLMConfigService(db_session)
    
    start = time.time()
    config = await service.get_global_config()
    elapsed = time.time() - start
    
    assert elapsed < 0.1  # Should load in < 100ms
```

#### 7.2 LLM Instantiation Time

**Test**: Measure time to create LLM instance

```python
@pytest.mark.asyncio
async def test_llm_instantiation_performance(db_session):
    service = LLMConfigService(db_session)
    
    start = time.time()
    llm = await service.get_llm_for_interaction(LLMInteractionType.REASONING)
    elapsed = time.time() - start
    
    assert elapsed < 0.5  # Should instantiate in < 500ms
```

### 8. Security Tests

#### 8.1 API Key Encryption

**Test**: Verify API keys are encrypted in database

```bash
docker-compose exec postgres psql -U ravenhelm -d ravenhelm_dev -c "
SELECT name, api_key_encrypted 
FROM llm_providers 
WHERE api_key_encrypted IS NOT NULL;
"
```

**Expected**: `api_key_encrypted` should NOT contain plaintext API key

#### 8.2 Secret Storage

**Test**: Verify secrets are in LocalStack

```bash
aws --endpoint-url=http://localhost:4566 \
  secretsmanager list-secrets | jq '.SecretList[] | select(.Name | contains("llm"))'
```

**Expected**: Secrets exist for each provider with API keys

## Manual Test Checklist

### Setup Phase
- [ ] Database migration runs successfully
- [ ] Seed script completes without errors
- [ ] Default configuration is created
- [ ] OpenAI provider validates successfully

### API Phase
- [ ] Can list providers
- [ ] Can add new provider
- [ ] Can validate provider
- [ ] Can fetch models from provider
- [ ] Can get global config
- [ ] Can update interaction config
- [ ] Can get config summary
- [ ] Can validate all configs

### UI Phase
- [ ] LLM Settings button appears on dashboard
- [ ] Settings panel opens
- [ ] Providers tab loads correctly
- [ ] Config tab loads correctly
- [ ] Can change model for interaction type
- [ ] Can adjust temperature
- [ ] Changes persist after refresh

### Integration Phase
- [ ] Norns uses configured model
- [ ] Subagents use configured model
- [ ] Planner uses configured model
- [ ] Muninn uses configured embeddings
- [ ] Chat works end-to-end with new config

### Error Handling Phase
- [ ] Invalid API key handled gracefully
- [ ] Unreachable server handled gracefully
- [ ] Missing config falls back to defaults
- [ ] UI shows errors appropriately

## Test Execution

### Automated Tests

```bash
# Run all tests
cd hlidskjalf
pytest tests/test_llm_*.py -v

# Run specific test file
pytest tests/test_llm_providers.py -v

# Run with coverage
pytest tests/test_llm_*.py --cov=src.services --cov=src.models.llm_config
```

### Manual Tests

Follow the checklist above, documenting results in a test log:

```
Date: 2025-12-06
Tester: Nate Walker
Environment: Local Docker

[✓] Setup Phase - All checks passed
[✓] API Phase - All endpoints working
[✓] UI Phase - Settings panel functional
[✓] Integration Phase - Norns using new config
[✓] Error Handling - Graceful degradation confirmed
```

## Success Criteria

The LLM configuration system is considered production-ready when:

1. ✅ All database tables exist and are populated
2. ✅ Default configuration is seeded automatically
3. ✅ All API endpoints return expected responses
4. ✅ UI loads and updates configuration correctly
5. ✅ Norns, subagents, planner, and Muninn use configured models
6. ✅ Error handling is graceful (no crashes)
7. ✅ API keys are encrypted and stored securely
8. ✅ Configuration changes persist across restarts
9. ✅ Performance is acceptable (< 500ms for LLM instantiation)
10. ✅ Documentation is complete and accurate

## Known Issues

None at this time. Document any issues discovered during testing here.

## Next Steps

After testing is complete:

1. Update `PROJECT_PLAN.md` to mark Phase complete
2. Document lessons learned in `docs/LESSONS_LEARNED.md`
3. Create GitLab issue for any bugs found
4. Plan next phase of work (user-specific overrides, cost tracking, etc.)


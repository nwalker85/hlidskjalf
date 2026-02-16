-- ============================================================================
-- Seed default LLM configuration
-- ============================================================================
-- This script creates a default OpenAI provider configuration
-- Note: API key must be added via UI or API after deployment

-- Create default OpenAI provider (disabled until API key is added)
INSERT INTO llm_providers (id, name, provider_type, enabled, validated_at, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'OpenAI',
    'OPENAI',
    false,  -- Disabled until API key is provided
    NULL,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
)
ON CONFLICT (name) DO NOTHING;

-- Get the provider ID for subsequent inserts
DO $$
DECLARE
    openai_provider_id UUID;
BEGIN
    SELECT id INTO openai_provider_id FROM llm_providers WHERE name = 'OpenAI';
    
    -- Insert default OpenAI models
    INSERT INTO llm_provider_models (id, provider_id, model_name, supports_tools, supports_embeddings, context_window, created_at)
    VALUES
        (gen_random_uuid(), openai_provider_id, 'gpt-4o', true, false, 128000, CURRENT_TIMESTAMP),
        (gen_random_uuid(), openai_provider_id, 'gpt-4o-mini', true, false, 128000, CURRENT_TIMESTAMP),
        (gen_random_uuid(), openai_provider_id, 'gpt-4-turbo', true, false, 128000, CURRENT_TIMESTAMP),
        (gen_random_uuid(), openai_provider_id, 'gpt-4', true, false, 8192, CURRENT_TIMESTAMP),
        (gen_random_uuid(), openai_provider_id, 'gpt-3.5-turbo', true, false, 16385, CURRENT_TIMESTAMP),
        (gen_random_uuid(), openai_provider_id, 'text-embedding-3-small', false, true, 8191, CURRENT_TIMESTAMP),
        (gen_random_uuid(), openai_provider_id, 'text-embedding-3-large', false, true, 8191, CURRENT_TIMESTAMP),
        (gen_random_uuid(), openai_provider_id, 'text-embedding-ada-002', false, true, 8191, CURRENT_TIMESTAMP)
    ON CONFLICT (provider_id, model_name) DO NOTHING;
    
    -- Insert default global configuration for all interaction types
    INSERT INTO llm_global_config (interaction_type, provider_id, model_name, temperature, updated_at)
    VALUES
        ('reasoning', openai_provider_id, 'gpt-4o', 0.7, CURRENT_TIMESTAMP),
        ('tools', openai_provider_id, 'gpt-4o-mini', 0.1, CURRENT_TIMESTAMP),
        ('subagents', openai_provider_id, 'gpt-4o-mini', 0.5, CURRENT_TIMESTAMP),
        ('planning', openai_provider_id, 'gpt-4o', 0.2, CURRENT_TIMESTAMP),
        ('embeddings', openai_provider_id, 'text-embedding-3-small', 0.0, CURRENT_TIMESTAMP)
    ON CONFLICT (interaction_type) DO UPDATE SET
        provider_id = EXCLUDED.provider_id,
        model_name = EXCLUDED.model_name,
        temperature = EXCLUDED.temperature,
        updated_at = EXCLUDED.updated_at;
END $$;

-- Display summary
SELECT 'LLM Configuration Seeded Successfully' AS status;
SELECT COUNT(*) AS provider_count FROM llm_providers;
SELECT COUNT(*) AS model_count FROM llm_provider_models;
SELECT COUNT(*) AS config_count FROM llm_global_config;


-- LLM Providers and Configuration Tables
-- Migration 002: Add support for cloud LLM providers and model configuration

-- Create enum for provider types
CREATE TYPE provider_type_enum AS ENUM ('openai', 'anthropic', 'custom');

-- Create enum for interaction types
CREATE TYPE interaction_type_enum AS ENUM ('reasoning', 'tools', 'subagents', 'planning', 'embeddings');

-- Table: llm_providers
-- Stores configured LLM providers (OpenAI, Anthropic, custom servers)
CREATE TABLE llm_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    provider_type provider_type_enum NOT NULL,
    api_base_url TEXT,  -- NULL for OpenAI/Anthropic (use default), required for custom
    api_key_secret_path TEXT,  -- Path in LocalStack Secrets Manager, e.g., 'ravenhelm/dev/llm/openai'
    enabled BOOLEAN DEFAULT TRUE,
    validated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Table: llm_provider_models
-- Models available from each provider
CREATE TABLE llm_provider_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES llm_providers(id) ON DELETE CASCADE,
    model_name VARCHAR(255) NOT NULL,
    supports_tools BOOLEAN DEFAULT TRUE,
    supports_embeddings BOOLEAN DEFAULT FALSE,
    context_window INTEGER DEFAULT 4096,
    cost_per_1k_input_tokens DECIMAL(10, 6),
    cost_per_1k_output_tokens DECIMAL(10, 6),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(provider_id, model_name)
);

-- Table: llm_global_config
-- Global default model configuration for each interaction type
CREATE TABLE llm_global_config (
    interaction_type interaction_type_enum PRIMARY KEY,
    provider_id UUID NOT NULL REFERENCES llm_providers(id) ON DELETE RESTRICT,
    model_name VARCHAR(255) NOT NULL,
    temperature DECIMAL(3, 2) DEFAULT 0.7,
    max_tokens INTEGER,
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (provider_id, model_name) REFERENCES llm_provider_models(provider_id, model_name) ON DELETE RESTRICT
);

-- Table: llm_user_config (optional, for multi-user support)
-- Per-user overrides of model configuration
CREATE TABLE llm_user_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    interaction_type interaction_type_enum NOT NULL,
    provider_id UUID NOT NULL REFERENCES llm_providers(id) ON DELETE CASCADE,
    model_name VARCHAR(255) NOT NULL,
    temperature DECIMAL(3, 2) DEFAULT 0.7,
    max_tokens INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, interaction_type),
    FOREIGN KEY (provider_id, model_name) REFERENCES llm_provider_models(provider_id, model_name) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_llm_providers_enabled ON llm_providers(enabled);
CREATE INDEX idx_llm_provider_models_provider ON llm_provider_models(provider_id);
CREATE INDEX idx_llm_user_config_user ON llm_user_config(user_id);
CREATE INDEX idx_llm_user_config_interaction ON llm_user_config(interaction_type);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_llm_providers_updated_at
    BEFORE UPDATE ON llm_providers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_llm_provider_models_updated_at
    BEFORE UPDATE ON llm_provider_models
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_llm_global_config_updated_at
    BEFORE UPDATE ON llm_global_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_llm_user_config_updated_at
    BEFORE UPDATE ON llm_user_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE llm_providers IS 'Configured LLM providers (OpenAI, Anthropic, custom OpenAI-compatible servers)';
COMMENT ON TABLE llm_provider_models IS 'Models available from each provider with capabilities and cost information';
COMMENT ON TABLE llm_global_config IS 'Global default model configuration for each interaction type';
COMMENT ON TABLE llm_user_config IS 'Per-user overrides of global model configuration';

COMMENT ON COLUMN llm_providers.api_key_secret_path IS 'Path to API key in LocalStack Secrets Manager';
COMMENT ON COLUMN llm_provider_models.supports_tools IS 'Whether model supports function/tool calling';
COMMENT ON COLUMN llm_provider_models.supports_embeddings IS 'Whether model is an embedding model';
COMMENT ON COLUMN llm_global_config.temperature IS 'Default temperature (0.0-2.0) for this interaction type';


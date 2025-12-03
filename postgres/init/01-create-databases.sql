-- ============================================================================
-- Ravenhelm Platform - PostgreSQL Initialization
-- ============================================================================
-- This runs on first PostgreSQL startup (pgvector/pgvector:pg16 image)

-- Enable pgvector extension (Muninn's semantic search capability)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- Platform Service Databases
-- ============================================================================

-- LangFuse (LLM Observability)
CREATE DATABASE langfuse;
GRANT ALL PRIVILEGES ON DATABASE langfuse TO postgres;

-- Enable vector in langfuse db
\c langfuse
CREATE EXTENSION IF NOT EXISTS vector;

-- Switch back to postgres db
\c postgres

-- ============================================================================
-- Hliðskjálf - Odin's High Seat (Control Plane)
-- ============================================================================

CREATE DATABASE hlidskjalf;
GRANT ALL PRIVILEGES ON DATABASE hlidskjalf TO postgres;

-- ============================================================================
-- Muninn Schema (Memory Manager)
-- ============================================================================
-- Schema for long-term memory storage
-- Used by agents for episodic → semantic memory promotion

CREATE SCHEMA IF NOT EXISTS muninn;

-- Episodic memories (user-specific experiences)
CREATE TABLE IF NOT EXISTS muninn.episodic_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    session_id UUID,
    agent_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),  -- OpenAI ada-002 dimensions
    importance_score FLOAT DEFAULT 0.5,
    access_count INT DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

-- Semantic memories (generalized knowledge promoted from episodic)
CREATE TABLE IF NOT EXISTS muninn.semantic_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    confidence_score FLOAT DEFAULT 0.5,
    source_episodic_ids UUID[] DEFAULT '{}',
    access_count INT DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Procedural memories (skills, workflows, learned patterns)
CREATE TABLE IF NOT EXISTS muninn.procedural_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    steps JSONB NOT NULL,
    embedding vector(1536),
    success_rate FLOAT DEFAULT 0.0,
    execution_count INT DEFAULT 0,
    last_executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Memory candidates (staging area for promotion)
CREATE TABLE IF NOT EXISTS muninn.memory_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,  -- episodic, observation, domain
    content TEXT NOT NULL,
    embedding vector(1536),
    relevance_signals JSONB DEFAULT '{}',
    promotion_score FLOAT DEFAULT 0.0,
    evaluated_at TIMESTAMPTZ,
    promoted_to_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for vector similarity search
CREATE INDEX IF NOT EXISTS idx_episodic_embedding ON muninn.episodic_memories 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_semantic_embedding ON muninn.semantic_memories 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_procedural_embedding ON muninn.procedural_memories 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_candidates_embedding ON muninn.memory_candidates 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_episodic_user ON muninn.episodic_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_episodic_agent ON muninn.episodic_memories(agent_id);
CREATE INDEX IF NOT EXISTS idx_semantic_domain ON muninn.semantic_memories(domain);

-- ============================================================================
-- n8n - Workflow Automation
-- ============================================================================

CREATE DATABASE n8n;
GRANT ALL PRIVILEGES ON DATABASE n8n TO postgres;

-- ============================================================================
-- Identity / Authorization
-- ============================================================================
CREATE DATABASE zitadel;
GRANT ALL PRIVILEGES ON DATABASE zitadel TO postgres;

-- ============================================================================
-- Future databases (uncomment as needed)
-- ============================================================================
-- CREATE DATABASE openfga;


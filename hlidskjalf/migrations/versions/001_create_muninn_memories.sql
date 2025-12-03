-- Muninn Memory Tables
-- Version: 001
-- Description: Create tables for Raven cognitive memory architecture

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Muninn Memories Table
-- =============================================================================
-- Main memory storage with weighting for Hel governance
CREATE TABLE IF NOT EXISTS muninn_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type TEXT NOT NULL CHECK (type IN ('episodic', 'semantic', 'procedural')),
    
    -- Content
    content TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT 'general',
    topic TEXT,
    summary TEXT,
    
    -- Embedding for semantic search
    embedding vector(1536),
    
    -- Hel governance
    weight FLOAT NOT NULL DEFAULT 0.5 CHECK (weight >= 0.0 AND weight <= 1.0),
    "references" INTEGER NOT NULL DEFAULT 0,
    
    -- Associations
    user_id TEXT,
    session_id TEXT,
    source_keys TEXT[],
    
    -- Features (flexible JSON)
    features JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_muninn_memories_type ON muninn_memories(type);
CREATE INDEX IF NOT EXISTS idx_muninn_memories_domain ON muninn_memories(domain);
CREATE INDEX IF NOT EXISTS idx_muninn_memories_user_id ON muninn_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_muninn_memories_session_id ON muninn_memories(session_id);
CREATE INDEX IF NOT EXISTS idx_muninn_memories_weight ON muninn_memories(weight DESC);
CREATE INDEX IF NOT EXISTS idx_muninn_memories_last_used ON muninn_memories(last_used);

-- Vector similarity index (IVFFlat for approximate nearest neighbor)
CREATE INDEX IF NOT EXISTS idx_muninn_memories_embedding 
    ON muninn_memories USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Composite index for common query pattern
CREATE INDEX IF NOT EXISTS idx_muninn_memories_type_domain_weight 
    ON muninn_memories(type, domain, weight DESC);

-- =============================================================================
-- Frigg Personas Table
-- =============================================================================
-- User persona snapshots for context
CREATE TABLE IF NOT EXISTS frigg_personas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Identity
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    
    -- Classification
    tags TEXT[] DEFAULT '{}',
    
    -- Preferences and flags
    preferences JSONB DEFAULT '{}',
    risk_flags JSONB DEFAULT '{}',
    regulatory_constraints TEXT[] DEFAULT '{}',
    
    -- Memory references
    memory_refs TEXT[] DEFAULT '{}',
    
    -- Role and actions
    current_role TEXT,
    applicable_triplets TEXT[] DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Unique per session
    UNIQUE(session_id)
);

CREATE INDEX IF NOT EXISTS idx_frigg_personas_user_id ON frigg_personas(user_id);
CREATE INDEX IF NOT EXISTS idx_frigg_personas_session_id ON frigg_personas(session_id);

-- =============================================================================
-- Muninn Episodes Table
-- =============================================================================
-- Interaction episodes for episodic memory
CREATE TABLE IF NOT EXISTS muninn_episodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Context
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    
    -- Content
    topic TEXT NOT NULL,
    summary TEXT,
    transcript JSONB DEFAULT '[]',
    
    -- Outcome
    outcome TEXT,
    satisfaction FLOAT,
    
    -- Metadata
    intent TEXT,
    entities JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    
    -- Timestamps
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_muninn_episodes_user_id ON muninn_episodes(user_id);
CREATE INDEX IF NOT EXISTS idx_muninn_episodes_session_id ON muninn_episodes(session_id);
CREATE INDEX IF NOT EXISTS idx_muninn_episodes_topic ON muninn_episodes(topic);
CREATE INDEX IF NOT EXISTS idx_muninn_episodes_started_at ON muninn_episodes(started_at DESC);

-- =============================================================================
-- Muninn Patterns Table
-- =============================================================================
-- Semantic patterns derived from episodes
CREATE TABLE IF NOT EXISTS muninn_patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Pattern definition
    pattern_type TEXT NOT NULL,
    description TEXT NOT NULL,
    
    -- Confidence and evidence
    confidence FLOAT NOT NULL DEFAULT 0.5,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    source_episodes UUID[] DEFAULT '{}',
    
    -- Domain and scope
    domain TEXT NOT NULL DEFAULT 'general',
    scope TEXT NOT NULL DEFAULT 'global',
    
    -- Pattern data
    conditions JSONB DEFAULT '{}',
    outcomes JSONB DEFAULT '{}',
    
    -- Embedding for semantic search
    embedding vector(1536),
    
    -- Metadata
    tags TEXT[] DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_validated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_muninn_patterns_type ON muninn_patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_muninn_patterns_domain ON muninn_patterns(domain);
CREATE INDEX IF NOT EXISTS idx_muninn_patterns_confidence ON muninn_patterns(confidence DESC);

-- Vector similarity index for patterns
CREATE INDEX IF NOT EXISTS idx_muninn_patterns_embedding 
    ON muninn_patterns USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

-- =============================================================================
-- Hel Governance Log
-- =============================================================================
-- Audit log for memory governance actions
CREATE TABLE IF NOT EXISTS hel_governance_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Action
    action TEXT NOT NULL CHECK (action IN ('reinforce', 'decay', 'promote', 'prune')),
    memory_id UUID,
    
    -- Before/after
    old_weight FLOAT,
    new_weight FLOAT,
    
    -- Context
    reason TEXT,
    context JSONB DEFAULT '{}',
    
    -- Timestamp
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hel_log_memory_id ON hel_governance_log(memory_id);
CREATE INDEX IF NOT EXISTS idx_hel_log_action ON hel_governance_log(action);
CREATE INDEX IF NOT EXISTS idx_hel_log_performed_at ON hel_governance_log(performed_at DESC);

-- =============================================================================
-- Functions
-- =============================================================================

-- Function to update last_used on memory access
CREATE OR REPLACE FUNCTION update_memory_last_used()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_used = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for memory updates
DROP TRIGGER IF EXISTS trigger_update_memory_last_used ON muninn_memories;
CREATE TRIGGER trigger_update_memory_last_used
    BEFORE UPDATE ON muninn_memories
    FOR EACH ROW
    EXECUTE FUNCTION update_memory_last_used();

-- Function for semantic search with weight consideration
CREATE OR REPLACE FUNCTION search_muninn_memories(
    query_embedding vector(1536),
    search_type TEXT DEFAULT NULL,
    search_domain TEXT DEFAULT NULL,
    min_weight FLOAT DEFAULT 0.0,
    result_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    type TEXT,
    content TEXT,
    domain TEXT,
    weight FLOAT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        m.type,
        m.content,
        m.domain,
        m.weight,
        (1 - (m.embedding <=> query_embedding))::FLOAT as similarity
    FROM muninn_memories m
    WHERE m.weight >= min_weight
        AND (search_type IS NULL OR m.type = search_type)
        AND (search_domain IS NULL OR m.domain = search_domain)
        AND m.embedding IS NOT NULL
    ORDER BY (m.weight * 0.3 + (1 - (m.embedding <=> query_embedding)) * 0.7) DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Comments
-- =============================================================================
COMMENT ON TABLE muninn_memories IS 'Muninn long-term memory storage with Hel governance';
COMMENT ON TABLE frigg_personas IS 'Frigg persona snapshots for user context';
COMMENT ON TABLE muninn_episodes IS 'Interaction episodes for episodic memory';
COMMENT ON TABLE muninn_patterns IS 'Semantic patterns derived from episodes';
COMMENT ON TABLE hel_governance_log IS 'Audit log for Hel memory governance actions';


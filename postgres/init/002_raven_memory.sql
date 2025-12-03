-- Raven Cognitive Memory Architecture
-- PostgreSQL initialization script
-- This script is run when the database container starts

\echo 'Creating Raven memory tables...'

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create hlidskjalf database if not exists
SELECT 'CREATE DATABASE hlidskjalf'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'hlidskjalf')\gexec

\c hlidskjalf

-- Enable extensions in hlidskjalf database
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- Muninn Memories Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS muninn_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type TEXT NOT NULL CHECK (type IN ('episodic', 'semantic', 'procedural')),
    content TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT 'general',
    topic TEXT,
    summary TEXT,
    embedding vector(1536),
    weight FLOAT NOT NULL DEFAULT 0.5 CHECK (weight >= 0.0 AND weight <= 1.0),
    "references" INTEGER NOT NULL DEFAULT 0,
    user_id TEXT,
    session_id TEXT,
    source_keys TEXT[],
    features JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_muninn_memories_type ON muninn_memories(type);
CREATE INDEX IF NOT EXISTS idx_muninn_memories_domain ON muninn_memories(domain);
CREATE INDEX IF NOT EXISTS idx_muninn_memories_user_id ON muninn_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_muninn_memories_weight ON muninn_memories(weight DESC);

-- =============================================================================
-- Frigg Personas Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS frigg_personas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    tags TEXT[] DEFAULT '{}',
    preferences JSONB DEFAULT '{}',
    risk_flags JSONB DEFAULT '{}',
    regulatory_constraints TEXT[] DEFAULT '{}',
    memory_refs TEXT[] DEFAULT '{}',
    current_role TEXT,
    applicable_triplets TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_frigg_personas_user_id ON frigg_personas(user_id);

-- =============================================================================
-- Muninn Episodes Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS muninn_episodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    summary TEXT,
    transcript JSONB DEFAULT '[]',
    outcome TEXT,
    satisfaction FLOAT,
    intent TEXT,
    entities JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_muninn_episodes_user_id ON muninn_episodes(user_id);

-- =============================================================================
-- Muninn Patterns Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS muninn_patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pattern_type TEXT NOT NULL,
    description TEXT NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.5,
    evidence_count INTEGER NOT NULL DEFAULT 0,
    source_episodes UUID[] DEFAULT '{}',
    domain TEXT NOT NULL DEFAULT 'general',
    scope TEXT NOT NULL DEFAULT 'global',
    conditions JSONB DEFAULT '{}',
    outcomes JSONB DEFAULT '{}',
    embedding vector(1536),
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_validated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Hel Governance Log
-- =============================================================================
CREATE TABLE IF NOT EXISTS hel_governance_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action TEXT NOT NULL CHECK (action IN ('reinforce', 'decay', 'promote', 'prune')),
    memory_id UUID,
    old_weight FLOAT,
    new_weight FLOAT,
    reason TEXT,
    context JSONB DEFAULT '{}',
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

\echo 'Raven memory tables created successfully!'


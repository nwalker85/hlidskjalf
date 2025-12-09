-- Procedural Memory Enhancements
-- Version: 003
-- Description: Schema enhancements for skills as procedural memories

-- =============================================================================
-- Add indexes for procedural memory queries
-- =============================================================================

-- Index for procedural memory type queries
CREATE INDEX IF NOT EXISTS idx_muninn_procedural 
  ON muninn_memories(type, domain, weight DESC) 
  WHERE type = 'procedural';

-- Index for skill topic queries
CREATE INDEX IF NOT EXISTS idx_muninn_procedural_topic 
  ON muninn_memories(type, topic, weight DESC) 
  WHERE type = 'procedural' AND topic = 'skill';

-- =============================================================================
-- Add metadata column if it doesn't exist
-- =============================================================================

-- JSONB column for flexible skill metadata
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'muninn_memories' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE muninn_memories 
          ADD COLUMN metadata JSONB DEFAULT '{}';
    END IF;
END $$;

-- =============================================================================
-- Add GIN indexes for JSONB queries
-- =============================================================================

-- Index for skill roles (JSONB array)
CREATE INDEX IF NOT EXISTS idx_muninn_skill_roles 
  ON muninn_memories USING gin ((features->'roles'))
  WHERE type = 'procedural';

-- Index for skill tags (JSONB array)
CREATE INDEX IF NOT EXISTS idx_muninn_skill_tags 
  ON muninn_memories USING gin ((features->'tags'))
  WHERE type = 'procedural';

-- Index for skill dependencies
CREATE INDEX IF NOT EXISTS idx_muninn_skill_dependencies 
  ON muninn_memories USING gin ((features->'dependencies'))
  WHERE type = 'procedural';

-- Index for source URL (semantic memories - documents)
CREATE INDEX IF NOT EXISTS idx_muninn_semantic_source_url 
  ON muninn_memories USING btree ((features->>'source_url'))
  WHERE type = 'semantic';

-- =============================================================================
-- Helper functions for skill queries
-- =============================================================================

-- Function to search skills by role
CREATE OR REPLACE FUNCTION search_skills_by_role(
    role_name TEXT,
    search_domain TEXT DEFAULT NULL,
    min_weight FLOAT DEFAULT 0.0,
    result_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    content TEXT,
    summary TEXT,
    weight FLOAT,
    references INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        (m.features->>'name')::TEXT as name,
        m.content,
        m.summary,
        m.weight,
        m.references
    FROM muninn_memories m
    WHERE m.type = 'procedural'
        AND m.topic = 'skill'
        AND m.weight >= min_weight
        AND m.features->'roles' ? role_name
        AND (search_domain IS NULL OR m.domain = search_domain)
        AND NOT COALESCE((m.features->>'deleted')::BOOLEAN, FALSE)
    ORDER BY m.weight DESC, m.references DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to get skill dependencies
CREATE OR REPLACE FUNCTION get_skill_dependencies(
    skill_id UUID
)
RETURNS TABLE (
    dependency_name TEXT,
    dependency_id UUID
) AS $$
BEGIN
    RETURN QUERY
    WITH skill_deps AS (
        SELECT jsonb_array_elements_text(features->'dependencies') as dep_name
        FROM muninn_memories
        WHERE id = skill_id AND type = 'procedural'
    )
    SELECT 
        deps.dep_name as dependency_name,
        m.id as dependency_id
    FROM skill_deps deps
    LEFT JOIN muninn_memories m 
        ON m.type = 'procedural' 
        AND m.topic = 'skill'
        AND (m.features->>'name') = deps.dep_name;
END;
$$ LANGUAGE plpgsql;

-- Function to get document crawl statistics
CREATE OR REPLACE FUNCTION get_document_stats(
    search_domain TEXT DEFAULT NULL
)
RETURNS TABLE (
    total_documents BIGINT,
    unique_urls BIGINT,
    avg_weight FLOAT,
    total_size BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_documents,
        COUNT(DISTINCT (features->>'source_url'))::BIGINT as unique_urls,
        AVG(weight)::FLOAT as avg_weight,
        SUM(LENGTH(content))::BIGINT as total_size
    FROM muninn_memories
    WHERE type = 'semantic'
        AND topic = 'document'
        AND (search_domain IS NULL OR domain = search_domain);
END;
$$ LANGUAGE plpgsql;

-- Function to find skills needing review (low weight, unused)
CREATE OR REPLACE FUNCTION find_skills_needing_review(
    weight_threshold FLOAT DEFAULT 0.2,
    days_unused INTEGER DEFAULT 30
)
RETURNS TABLE (
    id UUID,
    name TEXT,
    weight FLOAT,
    references INTEGER,
    days_since_use INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        (m.features->>'name')::TEXT as name,
        m.weight,
        m.references,
        EXTRACT(DAY FROM (NOW() - m.last_used))::INTEGER as days_since_use
    FROM muninn_memories m
    WHERE m.type = 'procedural'
        AND m.topic = 'skill'
        AND (
            m.weight < weight_threshold
            OR EXTRACT(DAY FROM (NOW() - m.last_used)) > days_unused
        )
        AND NOT COALESCE((m.features->>'deleted')::BOOLEAN, FALSE)
    ORDER BY m.weight ASC, m.last_used ASC;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Update statistics and maintenance
-- =============================================================================

-- Analyze tables for query optimization
ANALYZE muninn_memories;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON INDEX idx_muninn_procedural IS 'Optimizes procedural memory queries with domain and weight filters';
COMMENT ON INDEX idx_muninn_procedural_topic IS 'Optimizes skill-specific queries';
COMMENT ON INDEX idx_muninn_skill_roles IS 'Enables fast role-based skill lookups';
COMMENT ON INDEX idx_muninn_skill_tags IS 'Enables fast tag-based skill searches';
COMMENT ON INDEX idx_muninn_semantic_source_url IS 'Tracks document source URLs for deduplication';

COMMENT ON FUNCTION search_skills_by_role IS 'Search skills available to a specific role';
COMMENT ON FUNCTION get_skill_dependencies IS 'Get all dependencies for a skill';
COMMENT ON FUNCTION get_document_stats IS 'Get statistics about ingested documents';
COMMENT ON FUNCTION find_skills_needing_review IS 'Identify low-weight or unused skills for governance';


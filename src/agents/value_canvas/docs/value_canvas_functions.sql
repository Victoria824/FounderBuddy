-- Stored functions for Value Canvas agent
-- These functions need to be created in Supabase to support the agent's database operations

-- Function to get a specific section state
CREATE OR REPLACE FUNCTION get_section_state(
    p_user_id TEXT,
    p_doc_id TEXT,
    p_section_id TEXT
)
RETURNS TABLE (
    content JSONB,
    status TEXT,
    score INTEGER,
    updated_at TIMESTAMPTZ
) 
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ss.content,
        ss.status,
        ss.score,
        ss.updated_at
    FROM section_states ss
    WHERE ss.user_id = p_user_id::UUID
      AND ss.doc_id = p_doc_id::UUID
      AND ss.section_id = p_section_id
    LIMIT 1;
END;
$$;

-- Function to get all sections for a document
CREATE OR REPLACE FUNCTION get_document_sections(
    p_user_id TEXT,
    p_doc_id TEXT  
)
RETURNS TABLE (
    section_id TEXT,
    status TEXT,
    score INTEGER,
    has_content BOOLEAN,
    updated_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ss.section_id,
        ss.status,
        ss.score,
        (ss.content != '{"type": "doc", "content": []}')::BOOLEAN as has_content,
        ss.updated_at
    FROM section_states ss
    WHERE ss.user_id = p_user_id::UUID 
      AND ss.doc_id = p_doc_id::UUID
    ORDER BY ss.section_id;
END;
$$;

-- Grant execute permissions to authenticated users
GRANT EXECUTE ON FUNCTION get_section_state(TEXT, TEXT, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_document_sections(TEXT, TEXT) TO authenticated;

-- For anonymous access (if needed for public demos)
GRANT EXECUTE ON FUNCTION get_section_state(TEXT, TEXT, TEXT) TO anon;
GRANT EXECUTE ON FUNCTION get_document_sections(TEXT, TEXT) TO anon;
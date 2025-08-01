-- Migration for Value Canvas section_states table

-- Create section_states table
CREATE TABLE IF NOT EXISTS section_states (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    doc_id UUID NOT NULL,
    section_id TEXT NOT NULL,
    content JSONB DEFAULT '{"type": "doc", "content": []}',
    score INTEGER CHECK (score >= 0 AND score <= 5),
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint to prevent duplicate sections per document
    UNIQUE(user_id, doc_id, section_id)
);

-- Create indexes for performance
CREATE INDEX idx_section_states_user_doc ON section_states(user_id, doc_id);
CREATE INDEX idx_section_states_status ON section_states(status);
CREATE INDEX idx_section_states_updated ON section_states(updated_at DESC);

-- Create update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_section_states_updated_at 
    BEFORE UPDATE ON section_states 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security
ALTER TABLE section_states ENABLE ROW LEVEL SECURITY;

-- Create RLS policies (adjust based on your auth setup)
-- Policy for users to access their own sections
CREATE POLICY "Users can view own sections" ON section_states
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own sections" ON section_states
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sections" ON section_states
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own sections" ON section_states
    FOR DELETE USING (auth.uid() = user_id);

-- Create value_canvas_documents table for document metadata
CREATE TABLE IF NOT EXISTS value_canvas_documents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    export_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_vc_documents_user ON value_canvas_documents(user_id);
CREATE INDEX idx_vc_documents_completed ON value_canvas_documents(completed);

-- Enable RLS
ALTER TABLE value_canvas_documents ENABLE ROW LEVEL SECURITY;

-- RLS policies for documents
CREATE POLICY "Users can view own documents" ON value_canvas_documents
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own documents" ON value_canvas_documents
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own documents" ON value_canvas_documents
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own documents" ON value_canvas_documents
    FOR DELETE USING (auth.uid() = user_id);

-- Create realtime publication for section_states
ALTER PUBLICATION supabase_realtime ADD TABLE section_states;

-- Create helper function to get all sections for a document
CREATE OR REPLACE FUNCTION get_document_sections(p_user_id UUID, p_doc_id UUID)
RETURNS TABLE (
    section_id TEXT,
    status TEXT,
    score INTEGER,
    has_content BOOLEAN,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ss.section_id,
        ss.status,
        ss.score,
        (ss.content != '{"type": "doc", "content": []}')::BOOLEAN as has_content,
        ss.updated_at
    FROM section_states ss
    WHERE ss.user_id = p_user_id AND ss.doc_id = p_doc_id
    ORDER BY ss.section_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create function to check document completion
CREATE OR REPLACE FUNCTION check_document_completion(p_user_id UUID, p_doc_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    incomplete_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO incomplete_count
    FROM unnest(ARRAY[
        'interview', 'icp', 'pain_1', 'pain_2', 'pain_3',
        'payoff_1', 'payoff_2', 'payoff_3', 'signature_method',
        'mistakes', 'prize'
    ]) AS required_section(section_id)
    LEFT JOIN section_states ss 
        ON ss.section_id = required_section.section_id 
        AND ss.user_id = p_user_id 
        AND ss.doc_id = p_doc_id
    WHERE ss.status IS NULL OR ss.status != 'done';
    
    RETURN incomplete_count = 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
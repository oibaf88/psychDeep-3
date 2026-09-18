CREATE TABLE IF NOT EXISTS psychdeep_v12.knowledge_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    population_target VARCHAR(64) NOT NULL,
    clinical_objective VARCHAR(128) NOT NULL,
    content TEXT NOT NULL,
    evidence_level VARCHAR(64),
    contraindications TEXT,
    version VARCHAR(32) NOT NULL DEFAULT 'v1',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMP WITHOUT TIME ZONE,
    reviewed_by UUID REFERENCES psychdeep_v12.users(id) ON DELETE SET NULL
);

ALTER TABLE psychdeep_v12.knowledge_items OWNER TO psychdeep_backend;
ALTER TABLE psychdeep_v12.knowledge_items ENABLE ROW LEVEL SECURITY;

-- Admins can do anything
CREATE POLICY admin_knowledge_items_all
    ON psychdeep_v12.knowledge_items
    FOR ALL
    TO authenticated
    USING (
        (SELECT role FROM psychdeep_v12.users WHERE users.id = auth.uid()) IN ('admin_clinical')
    );

-- Any authenticated user can read active knowledge items
CREATE POLICY active_knowledge_items_read
    ON psychdeep_v12.knowledge_items
    FOR SELECT
    TO authenticated
    USING (
        is_active = true
    );


-- Add policy to allow backend full access
CREATE POLICY backend_full_access
    ON psychdeep_v12.knowledge_items
    FOR ALL
    TO psychdeep_backend
    USING (true);



-- Add sync_replication_access policy
CREATE POLICY sync_replication_access
    ON psychdeep_v12.knowledge_items
    FOR ALL
    TO psychdeep_sync
    USING (true);

-- Change ownership to backend

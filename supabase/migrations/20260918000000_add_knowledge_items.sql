CREATE TABLE IF NOT EXISTS public.knowledge_items (
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
    reviewed_by UUID REFERENCES public.users(id) ON DELETE SET NULL
);

ALTER TABLE public.knowledge_items ENABLE ROW LEVEL SECURITY;

-- Admins can do anything
CREATE POLICY admin_knowledge_items_all
    ON public.knowledge_items
    FOR ALL
    TO authenticated
    USING (
        (SELECT role FROM public.users WHERE users.id = auth.uid()) IN ('admin_clinical')
    );

-- Any authenticated user can read active knowledge items
CREATE POLICY active_knowledge_items_read
    ON public.knowledge_items
    FOR SELECT
    TO authenticated
    USING (
        is_active = true
    );

-- Keep `updated_at` current
CREATE TRIGGER knowledge_items_updated_at
    BEFORE UPDATE ON public.knowledge_items
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Longitudinal memory pipeline foundation (ADR-0005).
-- Expand-only: does not rewrite or delete legacy chat, diary or clinical-memory rows.
-- Payload content is never logged. All rows remain backend-only under forced RLS.

begin;
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

create table if not exists psychdeep_v12.memory_event_ledger (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    source_table varchar(64) not null,
    source_id uuid not null,
    channel varchar(24) not null,
    event_type varchar(48) not null default 'message',
    source_content_hash varchar(64) not null,
    event_at timestamptz,
    received_at timestamptz not null default now(),
    timezone_name varchar(64),
    consent_purpose varchar(48) not null,
    consent_snapshot jsonb not null default '{}'::jsonb,
    schema_version varchar(64) not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint ck_memory_event_source_table check (
        source_table in ('chat_messages', 'diary_entries', 'mobile_inference_events', 'external_interaction')
    ),
    constraint ck_memory_event_channel check (channel in ('chat', 'diary', 'mobile', 'external')),
    constraint ck_memory_event_consent check (
        consent_purpose in ('linguistic_analysis', 'data_processing', 'professional_sharing', 'research')
    ),
    constraint uq_memory_event_source unique (user_id, source_table, source_id)
);

create index if not exists ix_memory_event_user_event_at
    on psychdeep_v12.memory_event_ledger(user_id, event_at desc nulls last);
create index if not exists ix_memory_event_user_received
    on psychdeep_v12.memory_event_ledger(user_id, received_at desc);
create index if not exists ix_memory_event_hash
    on psychdeep_v12.memory_event_ledger(user_id, source_content_hash);

create table if not exists psychdeep_v12.memory_items (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    item_type varchar(48) not null,
    subject_ref varchar(160),
    perspective varchar(32) not null default 'user_report',
    attribution varchar(64) not null,
    content text not null,
    normalized_key varchar(256),
    confidence numeric(5,4),
    uncertainty varchar(16) not null default 'high',
    temporal_scope jsonb not null default '{}'::jsonb,
    source_refs jsonb not null default '[]'::jsonb,
    status varchar(24) not null default 'active',
    supersedes_id uuid references psychdeep_v12.memory_items(id) on delete set null,
    expires_at timestamptz,
    sensitivity varchar(24) not null default 'clinical',
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    schema_version varchar(64) not null,
    created_at timestamptz not null default now(),
    constraint ck_memory_item_type check (item_type in (
        'preference', 'goal', 'open_thread', 'episode', 'world_claim',
        'psychological_hypothesis', 'recurring_theme', 'contradiction',
        'correction', 'plan', 'relationship_context', 'manner_observation',
        'longitudinal_pattern', 'other'
    )),
    constraint ck_memory_item_perspective check (perspective in (
        'user_report', 'professional_report', 'assistant_hypothesis',
        'third_party_reported', 'system_observation', 'derived_pattern'
    )),
    constraint ck_memory_item_uncertainty check (uncertainty in ('low', 'medium', 'high', 'unknown')),
    constraint ck_memory_item_status check (status in ('active', 'superseded', 'retracted', 'expired', 'needs_review')),
    constraint ck_memory_item_confidence check (confidence is null or (confidence >= 0 and confidence <= 1))
);

create index if not exists ix_memory_items_user_type_status
    on psychdeep_v12.memory_items(user_id, item_type, status, created_at desc);
create index if not exists ix_memory_items_user_created
    on psychdeep_v12.memory_items(user_id, created_at desc);
create index if not exists ix_memory_items_expiry
    on psychdeep_v12.memory_items(user_id, expires_at) where status = 'active';
create index if not exists ix_memory_items_normalized
    on psychdeep_v12.memory_items(user_id, normalized_key) where normalized_key is not null;

create table if not exists psychdeep_v12.memory_item_sources (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    memory_item_id uuid not null references psychdeep_v12.memory_items(id) on delete cascade,
    source_type varchar(48) not null,
    source_id uuid not null,
    source_message_id uuid,
    role varchar(24),
    speaker_id varchar(160),
    source_at timestamptz,
    quote_hash varchar(64),
    relation varchar(32) not null default 'supports',
    created_at timestamptz not null default now(),
    constraint ck_memory_item_source_relation check (relation in (
        'supports', 'contradicts', 'corrects', 'context', 'derived_from'
    )),
    constraint uq_memory_item_source unique (memory_item_id, source_type, source_id, source_message_id, relation)
);

create index if not exists ix_memory_item_sources_item
    on psychdeep_v12.memory_item_sources(user_id, memory_item_id);
create index if not exists ix_memory_item_sources_source
    on psychdeep_v12.memory_item_sources(user_id, source_type, source_id);

create table if not exists psychdeep_v12.memory_summary_versions (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    scope_type varchar(32) not null,
    scope_key varchar(160) not null default 'global',
    l0 text not null default '',
    l1 text not null default '',
    l2 text not null default '',
    source_watermark timestamptz,
    source_refs jsonb not null default '[]'::jsonb,
    source_digest varchar(64) not null,
    supersedes_id uuid references psychdeep_v12.memory_summary_versions(id) on delete set null,
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    prompt_version varchar(96) not null,
    schema_version varchar(64) not null,
    generation_reason varchar(48) not null default 'incremental',
    status varchar(24) not null default 'active',
    created_at timestamptz not null default now(),
    constraint ck_memory_summary_scope check (
        scope_type in ('global', 'topic', 'episode', 'time_window', 'relationship', 'goal')
    ),
    constraint ck_memory_summary_status check (status in ('active', 'superseded', 'failed', 'needs_review')),
    constraint ck_memory_summary_l0 check (char_length(l0) <= 256),
    constraint ck_memory_summary_l1 check (char_length(l1) <= 4000)
);

create index if not exists ix_memory_summary_current
    on psychdeep_v12.memory_summary_versions(user_id, scope_type, scope_key, status, created_at desc);
create index if not exists ix_memory_summary_watermark
    on psychdeep_v12.memory_summary_versions(user_id, source_watermark desc nulls last);

create table if not exists psychdeep_v12.memory_jobs (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    job_type varchar(48) not null,
    source_table varchar(64) not null,
    source_id uuid not null,
    idempotency_key varchar(192) not null,
    status varchar(24) not null default 'pending',
    attempts integer not null default 0,
    max_attempts integer not null default 5,
    available_at timestamptz not null default now(),
    locked_at timestamptz,
    completed_at timestamptz,
    error_category varchar(64),
    output_refs jsonb not null default '[]'::jsonb,
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint ck_memory_job_type check (job_type in (
        'extract_items', 'refresh_summary', 'embed_items', 'detect_contradictions',
        'longitudinal_analysis', 'opencontext_sync'
    )),
    constraint ck_memory_job_status check (status in (
        'pending', 'processing', 'succeeded', 'retry', 'dead_letter', 'cancelled'
    )),
    constraint ck_memory_job_attempts check (attempts >= 0 and max_attempts > 0),
    constraint uq_memory_job_idempotency unique (user_id, job_type, idempotency_key)
);

create index if not exists ix_memory_jobs_ready
    on psychdeep_v12.memory_jobs(status, available_at, created_at)
    where status in ('pending', 'retry');
create index if not exists ix_memory_jobs_user
    on psychdeep_v12.memory_jobs(user_id, created_at desc);

create table if not exists psychdeep_v12.memory_retrieval_runs (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    task_type varchar(48) not null,
    retrieval_version varchar(64) not null,
    query_hash varchar(64) not null,
    selected_refs jsonb not null default '[]'::jsonb,
    source_coverage jsonb not null default '{}'::jsonb,
    estimated_tokens integer not null default 0,
    actual_input_tokens integer,
    budget_tokens integer not null,
    latency_ms integer,
    truncation jsonb not null default '{}'::jsonb,
    status varchar(24) not null,
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint ck_memory_retrieval_task check (task_type in (
        'conversation', 'longitudinal_analysis', 'professional_review', 'crisis', 'psychoeducation', 'copilot'
    )),
    constraint ck_memory_retrieval_status check (status in ('succeeded', 'partial', 'failed', 'no_results')),
    constraint ck_memory_retrieval_budget check (budget_tokens >= 0 and estimated_tokens >= 0)
);

create index if not exists ix_memory_retrieval_user_created
    on psychdeep_v12.memory_retrieval_runs(user_id, created_at desc);

-- Force row isolation at the database boundary. These tables are backend-only:
-- no direct grants to patient-facing PostgREST roles.
do $$
declare
    table_name text;
begin
    foreach table_name in array array[
        'memory_event_ledger',
        'memory_items',
        'memory_item_sources',
        'memory_summary_versions',
        'memory_jobs',
        'memory_retrieval_runs'
    ]
    loop
        execute format('alter table psychdeep_v12.%I enable row level security', table_name);
        execute format('alter table psychdeep_v12.%I force row level security', table_name);
        execute format('drop policy if exists backend_full_access on psychdeep_v12.%I', table_name);
        execute format(
            'create policy backend_full_access on psychdeep_v12.%I for all to psychdeep_backend using (true) with check (true)',
            table_name
        );
        execute format(
            'revoke all on table psychdeep_v12.%I from public, anon, authenticated, service_role',
            table_name
        );
    end loop;
end
$$;

reset role;
revoke psychdeep_backend from postgres granted by postgres;

do $$
declare
    table_name text;
    hardened boolean;
    policy_exists boolean;
begin
    foreach table_name in array array[
        'memory_event_ledger',
        'memory_items',
        'memory_item_sources',
        'memory_summary_versions',
        'memory_jobs',
        'memory_retrieval_runs'
    ]
    loop
        select owner_role.rolname = 'psychdeep_backend'
           and relation.relrowsecurity
           and relation.relforcerowsecurity
          into hardened
          from pg_class relation
          join pg_namespace namespace on namespace.oid = relation.relnamespace
          join pg_roles owner_role on owner_role.oid = relation.relowner
         where namespace.nspname = 'psychdeep_v12'
           and relation.relname = table_name;

        select exists (
            select 1 from pg_policies
             where schemaname = 'psychdeep_v12'
               and tablename = table_name
               and policyname = 'backend_full_access'
               and 'psychdeep_backend' = any(roles)
        ) into policy_exists;

        if not coalesce(hardened, false) then
            raise exception '% owner/RLS hardening is incomplete', table_name;
        end if;
        if not policy_exists then
            raise exception '% backend RLS policy is missing', table_name;
        end if;
    end loop;
end
$$;

commit;

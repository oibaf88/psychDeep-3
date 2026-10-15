-- Whole-person longitudinal patient model (ADR-0006).
-- Expand-only. The original conversational/diary record and ADR-0002 memory remain canonical.
-- Episodes, relations, model versions and questions are derived, traceable projections.

begin;
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

create table if not exists psychdeep_v12.memory_episodes (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    episode_key varchar(192) not null,
    title varchar(240) not null,
    start_at timestamptz,
    end_at timestamptz,
    l0 text not null default '',
    l1 text not null default '',
    l2 text not null default '',
    source_refs jsonb not null default '[]'::jsonb,
    themes jsonb not null default '[]'::jsonb,
    transitions jsonb not null default '[]'::jsonb,
    uncertainty varchar(16) not null default 'unknown',
    status varchar(24) not null default 'active',
    source_digest varchar(64) not null,
    supersedes_id uuid references psychdeep_v12.memory_episodes(id) on delete set null,
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    prompt_version varchar(96) not null,
    schema_version varchar(64) not null,
    created_at timestamptz not null default now(),
    constraint uq_memory_episode_key unique (user_id, episode_key, source_digest),
    constraint ck_memory_episode_uncertainty check (uncertainty in ('low', 'medium', 'high', 'unknown')),
    constraint ck_memory_episode_status check (status in ('active', 'superseded', 'needs_review', 'archived')),
    constraint ck_memory_episode_l0 check (char_length(l0) <= 512),
    constraint ck_memory_episode_l1 check (char_length(l1) <= 6000)
);

create index if not exists ix_memory_episodes_user_time
    on psychdeep_v12.memory_episodes(user_id, start_at desc nulls last, end_at desc nulls last);
create index if not exists ix_memory_episodes_user_status
    on psychdeep_v12.memory_episodes(user_id, status, created_at desc);

create table if not exists psychdeep_v12.memory_relations (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    from_item_id uuid not null references psychdeep_v12.memory_items(id) on delete cascade,
    to_item_id uuid not null references psychdeep_v12.memory_items(id) on delete cascade,
    relation_type varchar(40) not null,
    evidence_refs jsonb not null default '[]'::jsonb,
    rationale text not null default '',
    confidence numeric(5,4),
    uncertainty varchar(16) not null default 'unknown',
    status varchar(24) not null default 'provisional',
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint ck_memory_relation_not_self check (from_item_id <> to_item_id),
    constraint ck_memory_relation_type check (relation_type in (
        'supports', 'contradicts', 'corrects', 'repeats', 'co_occurs',
        'precedes', 'follows', 'part_of_episode', 'pattern_of',
        'possible_trigger', 'possible_protective_factor', 'supersedes',
        'context_of', 'associated_with'
    )),
    constraint ck_memory_relation_uncertainty check (uncertainty in ('low', 'medium', 'high', 'unknown')),
    constraint ck_memory_relation_status check (status in ('provisional', 'accepted', 'rejected', 'superseded')),
    constraint ck_memory_relation_confidence check (confidence is null or (confidence >= 0 and confidence <= 1)),
    constraint uq_memory_relation unique (user_id, from_item_id, to_item_id, relation_type)
);

create index if not exists ix_memory_relations_from
    on psychdeep_v12.memory_relations(user_id, from_item_id, relation_type);
create index if not exists ix_memory_relations_to
    on psychdeep_v12.memory_relations(user_id, to_item_id, relation_type);

create table if not exists psychdeep_v12.patient_model_versions (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    version_no integer not null,
    model_schema_version varchar(64) not null,
    model_json jsonb not null,
    evidence_refs jsonb not null default '[]'::jsonb,
    coverage jsonb not null default '{}'::jsonb,
    unresolved_contradictions jsonb not null default '[]'::jsonb,
    unanswered_questions jsonb not null default '[]'::jsonb,
    source_watermark timestamptz,
    source_digest varchar(64) not null,
    supersedes_id uuid references psychdeep_v12.patient_model_versions(id) on delete set null,
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    prompt_version varchar(96) not null,
    status varchar(24) not null default 'provisional',
    created_at timestamptz not null default now(),
    constraint uq_patient_model_version unique (user_id, version_no),
    constraint ck_patient_model_version_positive check (version_no > 0),
    constraint ck_patient_model_status check (status in ('provisional', 'active', 'superseded', 'needs_review', 'failed'))
);

create index if not exists ix_patient_model_latest
    on psychdeep_v12.patient_model_versions(user_id, status, version_no desc);
create index if not exists ix_patient_model_watermark
    on psychdeep_v12.patient_model_versions(user_id, source_watermark desc nulls last);

create table if not exists psychdeep_v12.patient_model_questions (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    topic_key varchar(160) not null,
    question text not null,
    rationale text not null default '',
    priority smallint not null default 3,
    evidence_refs jsonb not null default '[]'::jsonb,
    status varchar(24) not null default 'open',
    decline_count integer not null default 0,
    last_asked_at timestamptz,
    snoozed_until timestamptz,
    created_by_model_version_id uuid references psychdeep_v12.patient_model_versions(id) on delete set null,
    resolved_by_source_ref varchar(192),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_patient_model_question unique (user_id, topic_key, question),
    constraint ck_patient_model_question_priority check (priority between 1 and 5),
    constraint ck_patient_model_question_status check (status in ('open', 'snoozed', 'answered', 'declined', 'obsolete')),
    constraint ck_patient_model_question_declines check (decline_count >= 0)
);

create index if not exists ix_patient_model_questions_queue
    on psychdeep_v12.patient_model_questions(user_id, status, priority, updated_at desc);

create table if not exists psychdeep_v12.memory_analysis_runs (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    analysis_type varchar(48) not null,
    question_hash varchar(64) not null,
    question_label varchar(240) not null default '',
    window_start timestamptz,
    window_end timestamptz,
    source_watermark timestamptz,
    evidence_refs jsonb not null default '[]'::jsonb,
    result_json jsonb not null default '{}'::jsonb,
    limitations jsonb not null default '[]'::jsonb,
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    prompt_version varchar(96) not null,
    schema_version varchar(64) not null,
    estimated_input_tokens integer,
    actual_input_tokens integer,
    output_tokens integer,
    status varchar(24) not null default 'pending',
    error_category varchar(64),
    created_at timestamptz not null default now(),
    completed_at timestamptz,
    constraint ck_memory_analysis_type check (analysis_type in (
        'whole_person', 'episode', 'trajectory', 'contradiction_review',
        'protective_factors', 'theme_silence', 'question'
    )),
    constraint ck_memory_analysis_status check (status in (
        'pending', 'processing', 'succeeded', 'partial', 'failed', 'cancelled'
    )),
    constraint ck_memory_analysis_tokens check (
        (estimated_input_tokens is null or estimated_input_tokens >= 0) and
        (actual_input_tokens is null or actual_input_tokens >= 0) and
        (output_tokens is null or output_tokens >= 0)
    )
);

create index if not exists ix_memory_analysis_user_created
    on psychdeep_v12.memory_analysis_runs(user_id, created_at desc);
create index if not exists ix_memory_analysis_hash
    on psychdeep_v12.memory_analysis_runs(user_id, analysis_type, question_hash, created_at desc);

do $$
declare
    table_name text;
begin
    foreach table_name in array array[
        'memory_episodes',
        'memory_relations',
        'patient_model_versions',
        'patient_model_questions',
        'memory_analysis_runs'
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
        'memory_episodes',
        'memory_relations',
        'patient_model_versions',
        'patient_model_questions',
        'memory_analysis_runs'
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

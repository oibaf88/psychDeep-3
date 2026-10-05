-- Clinical long-term memory (ADR-0002).
-- Expand-only. Discourse facts, psychological readings, formulation versions,
-- commit archives, professional notes, attention notices and optional embeddings.
-- Backend-only. Patients have no direct table privilege and no edit path.

begin;

do $$
begin
    create extension if not exists vector;
exception
    when others then
        raise notice 'pgvector unavailable; lexical retrieval remains authoritative: %', sqlerrm;
end
$$;

grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

create table if not exists psychdeep_v12.memory_commits (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    channel varchar(16) not null,
    source_id uuid not null,
    archive_abstract text not null default '',
    archive_overview text not null default '',
    source_ids jsonb not null default '[]'::jsonb,
    status varchar(16) not null,
    diff jsonb not null default '{}'::jsonb,
    correlation_id uuid,
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    prompt_version varchar(96) not null,
    policy_version varchar(96) not null,
    created_at timestamptz not null default now(),
    constraint ck_memory_commit_channel check (channel in ('chat', 'diary')),
    constraint ck_memory_commit_status check (status in ('accepted', 'skipped', 'failed'))
);

create table if not exists psychdeep_v12.discourse_facts (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    channel varchar(16) not null,
    quote text not null,
    spoken_at timestamptz not null,
    manner jsonb not null default '{}'::jsonb,
    chat_message_id uuid references psychdeep_v12.chat_messages(id) on delete set null,
    diary_entry_id uuid references psychdeep_v12.diary_entries(id) on delete set null,
    memory_commit_id uuid references psychdeep_v12.memory_commits(id) on delete set null,
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint ck_discourse_fact_channel check (channel in ('chat', 'diary'))
);

create table if not exists psychdeep_v12.psych_readings (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    hypothesis text not null,
    uncertainty varchar(16) not null,
    kind varchar(48) not null,
    evidence_refs jsonb not null default '[]'::jsonb,
    status varchar(16) not null default 'active',
    supersedes_id uuid references psychdeep_v12.psych_readings(id) on delete set null,
    memory_commit_id uuid references psychdeep_v12.memory_commits(id) on delete set null,
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint ck_psych_reading_uncertainty check (uncertainty in ('low', 'medium', 'high')),
    constraint ck_psych_reading_kind check (kind in (
        'recurrent_topic', 'manner_shift', 'contradiction', 'avoidance',
        'acute_new_topic', 'world_claim_unverified'
    )),
    constraint ck_psych_reading_status check (status in ('active', 'superseded'))
);

create table if not exists psychdeep_v12.formulation_versions (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    l0 text not null,
    l1 text not null,
    l2 text not null,
    supersedes_id uuid references psychdeep_v12.formulation_versions(id) on delete set null,
    prompt_version varchar(96) not null,
    policy_version varchar(96) not null,
    memory_commit_id uuid references psychdeep_v12.memory_commits(id) on delete set null,
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    acute_episode boolean not null default false,
    created_at timestamptz not null default now(),
    constraint ck_formulation_l0_len check (char_length(l0) <= 256),
    constraint ck_formulation_l1_len check (char_length(l1) <= 4000)
);

create table if not exists psychdeep_v12.memory_annotations (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    author_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    body text not null,
    target_type varchar(24) not null,
    target_id uuid not null,
    created_at timestamptz not null default now(),
    constraint ck_memory_annotation_target check (target_type in ('discourse', 'reading', 'formulation')),
    constraint ck_memory_annotation_body check (char_length(btrim(body)) > 0)
);

create table if not exists psychdeep_v12.clinical_attention_notices (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    reason varchar(48) not null,
    evidence_refs jsonb not null default '{}'::jsonb,
    status varchar(16) not null default 'open',
    acknowledged_at timestamptz,
    acknowledged_by uuid references psychdeep_v12.users(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint ck_attention_reason check (reason in (
        'medication_talk_without_act', 'manner_shift', 'contradiction',
        'avoidance', 'acute_new_topic'
    )),
    constraint ck_attention_status check (status in ('open', 'acknowledged'))
);

create table if not exists psychdeep_v12.memory_embeddings (
    id uuid primary key,
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    target_type varchar(24) not null,
    target_id uuid not null,
    embedding jsonb,
    provider varchar(96) not null,
    embedding_model varchar(192) not null,
    created_at timestamptz not null default now(),
    constraint ck_memory_embedding_target check (target_type in ('discourse', 'formulation'))
);

create index if not exists ix_memory_commits_user_created on psychdeep_v12.memory_commits(user_id, created_at desc);
create index if not exists ix_discourse_facts_user_spoken on psychdeep_v12.discourse_facts(user_id, spoken_at desc);
create index if not exists ix_psych_readings_user_status on psychdeep_v12.psych_readings(user_id, status, created_at desc);
create index if not exists ix_formulation_versions_user_created on psychdeep_v12.formulation_versions(user_id, created_at desc);
create index if not exists ix_memory_annotations_user_created on psychdeep_v12.memory_annotations(user_id, created_at desc);
create index if not exists ix_attention_notices_user_status on psychdeep_v12.clinical_attention_notices(user_id, status, created_at desc);
create index if not exists ix_memory_embeddings_target on psychdeep_v12.memory_embeddings(target_type, target_id);

do $$
declare
    table_name text;
begin
    foreach table_name in array array[
        'memory_commits',
        'discourse_facts',
        'psych_readings',
        'formulation_versions',
        'memory_annotations',
        'clinical_attention_notices',
        'memory_embeddings'
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

-- Optional index column. The application stores the vector as jsonb and does
-- not require this column. A missing extension must not fail the migration.
do $$
begin
    if exists (select 1 from pg_type where typname = 'vector') then
        execute 'alter table psychdeep_v12.memory_embeddings add column if not exists embedding_vector vector(1536)';
    end if;
exception
    when others then
        raise notice 'embedding_vector column skipped: %', sqlerrm;
end
$$;

do $$
declare
    table_name text;
    hardened boolean;
    policy_exists boolean;
begin
    foreach table_name in array array[
        'memory_commits',
        'discourse_facts',
        'psych_readings',
        'formulation_versions',
        'memory_annotations',
        'clinical_attention_notices',
        'memory_embeddings'
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

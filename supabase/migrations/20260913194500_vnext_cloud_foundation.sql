-- PsychDeep vNext: canonical longitudinal data foundation for hybrid cloud/mobile inference.
-- Expand-only: legacy clinical tables remain authoritative/legible while vNext
-- endpoints migrate. New tables are backend-only, FORCE RLS, and are NOT
-- granted to the retired SymmetricDS role.

begin;

-- Match the existing production ownership model. Abort rather than create a
-- clinical table with the wrong owner/policies.
do $$
declare
    membership_is_expected boolean;
begin
    select count(*) = 1
       and bool_and(m.admin_option)
       and not bool_or(m.inherit_option)
       and not bool_or(m.set_option)
       and bool_and(grantor.rolname = 'supabase_admin')
      into membership_is_expected
      from pg_auth_members m
      join pg_roles granted_role on granted_role.oid = m.roleid
      join pg_roles member_role on member_role.oid = m.member
      join pg_roles grantor on grantor.oid = m.grantor
     where granted_role.rolname = 'psychdeep_backend'
       and member_role.rolname = 'postgres';

    if not coalesce(membership_is_expected, false) then
        raise exception 'Unexpected postgres -> psychdeep_backend membership; migration stopped safely';
    end if;
end
$$;

grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

-- ---------------------------------------------------------------------
-- Canonical data plane
-- ---------------------------------------------------------------------
create table if not exists psychdeep_v12.observations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    source varchar(64) not null,
    type varchar(96) not null,
    value jsonb not null,
    unit varchar(48),
    occurred_at timestamptz not null,
    received_at timestamptz not null default now(),
    timezone varchar(64),
    quality jsonb not null default '{}'::jsonb,
    consent_id uuid references psychdeep_v12.user_consents(id) on delete set null,
    legacy_source_table varchar(64),
    legacy_source_id uuid,
    legacy_source_field varchar(64),
    created_at timestamptz not null default now()
);
create index if not exists ix_observations_user_occurred
    on psychdeep_v12.observations(user_id, occurred_at desc);
create index if not exists ix_observations_user_type_occurred
    on psychdeep_v12.observations(user_id, type, occurred_at desc);
create unique index if not exists ux_observations_legacy_source
    on psychdeep_v12.observations(legacy_source_table, legacy_source_id, legacy_source_field)
    where legacy_source_id is not null;

create table if not exists psychdeep_v12.feature_definitions (
    id uuid primary key default gen_random_uuid(),
    feature_key varchar(96) not null,
    version varchar(64) not null,
    formula text not null,
    unit varchar(48),
    window_spec jsonb not null default '{}'::jsonb,
    missingness_policy text not null,
    valid_range jsonb,
    status varchar(24) not null default 'active',
    created_at timestamptz not null default now(),
    unique(feature_key, version),
    constraint ck_feature_definition_status check (status in ('draft','active','retired'))
);

create table if not exists psychdeep_v12.feature_values (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    feature_key varchar(96) not null,
    feature_version varchar(64) not null,
    value jsonb not null,
    window_start timestamptz,
    window_end timestamptz,
    observation_refs jsonb not null default '[]'::jsonb,
    algorithm_version varchar(64) not null,
    quality_flags jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);
create index if not exists ix_feature_values_user_feature_created
    on psychdeep_v12.feature_values(user_id, feature_key, created_at desc);

create table if not exists psychdeep_v12.baseline_versions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    feature_key varchar(96),
    window_start timestamptz not null,
    window_end timestamptz not null,
    stats jsonb not null,
    exclusions jsonb not null default '[]'::jsonb,
    stability varchar(32) not null default 'unknown',
    data_coverage double precision,
    status varchar(24) not null default 'provisional',
    algorithm_version varchar(64) not null,
    legacy_baseline_id uuid,
    created_at timestamptz not null default now(),
    constraint ck_baseline_version_status check (status in ('provisional','active','frozen','retired')),
    constraint ck_baseline_coverage check (data_coverage is null or (data_coverage >= 0 and data_coverage <= 1))
);
create unique index if not exists ux_baseline_versions_legacy
    on psychdeep_v12.baseline_versions(legacy_baseline_id)
    where legacy_baseline_id is not null;
create index if not exists ix_baseline_versions_user_created
    on psychdeep_v12.baseline_versions(user_id, created_at desc);

create table if not exists psychdeep_v12.change_signals (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    feature varchar(96) not null,
    window_start timestamptz,
    window_end timestamptz,
    change_value double precision,
    band varchar(32) not null,
    uncertainty jsonb not null default '{}'::jsonb,
    evidence_refs jsonb not null default '[]'::jsonb,
    contradictions jsonb not null default '[]'::jsonb,
    baseline_version_id uuid references psychdeep_v12.baseline_versions(id) on delete set null,
    algorithm_version varchar(64) not null,
    legacy_signal_id uuid,
    created_at timestamptz not null default now(),
    constraint ck_change_signal_band check (band in ('stable','transition','unstable','insufficient_data','unknown'))
);
create unique index if not exists ux_change_signals_legacy
    on psychdeep_v12.change_signals(legacy_signal_id)
    where legacy_signal_id is not null;
create index if not exists ix_change_signals_user_created
    on psychdeep_v12.change_signals(user_id, created_at desc);

create table if not exists psychdeep_v12.model_runs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references psychdeep_v12.users(id) on delete set null,
    purpose varchar(96) not null,
    audience varchar(32) not null,
    deployment_alias varchar(96) not null,
    provider_type varchar(48) not null,
    model_id varchar(192) not null,
    model_version varchar(192),
    prompt_version varchar(96),
    policy_version varchar(96) not null,
    input_hash varchar(64) not null,
    output_schema varchar(96),
    status varchar(32) not null,
    correlation_id uuid,
    latency_ms integer,
    input_tokens integer,
    output_tokens integer,
    created_at timestamptz not null default now(),
    constraint ck_model_run_status check (status in ('started','succeeded','refused','invalid_output','provider_error','timeout','configuration_error','unavailable','abandoned')),
    constraint ck_model_run_latency check (latency_ms is null or latency_ms >= 0),
    constraint ck_model_run_input_tokens check (input_tokens is null or input_tokens >= 0),
    constraint ck_model_run_output_tokens check (output_tokens is null or output_tokens >= 0)
);
create index if not exists ix_model_runs_user_created
    on psychdeep_v12.model_runs(user_id, created_at desc);
create index if not exists ix_model_runs_correlation
    on psychdeep_v12.model_runs(correlation_id) where correlation_id is not null;

create table if not exists psychdeep_v12.inferences (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    kind varchar(96) not null,
    payload jsonb not null,
    evidence_refs jsonb not null default '[]'::jsonb,
    contradictions jsonb not null default '[]'::jsonb,
    uncertainty jsonb not null default '{}'::jsonb,
    status varchar(24) not null default 'active',
    expires_at timestamptz,
    algorithm_version varchar(64) not null,
    model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null,
    legacy_signal_id uuid,
    created_at timestamptz not null default now(),
    constraint ck_inference_status check (status in ('active','confirmed','refuted','expired','retired'))
);
create unique index if not exists ux_inferences_legacy
    on psychdeep_v12.inferences(legacy_signal_id)
    where legacy_signal_id is not null;
create index if not exists ix_inferences_user_created
    on psychdeep_v12.inferences(user_id, created_at desc);

create table if not exists psychdeep_v12.intervention_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    action_id varchar(96) not null,
    state varchar(24) not null,
    reason text,
    authority varchar(48) not null,
    burden varchar(24),
    usefulness smallint,
    source varchar(48) not null,
    proposed_at timestamptz not null default now(),
    acted_at timestamptz,
    correlation_id uuid,
    created_at timestamptz not null default now(),
    constraint ck_intervention_state check (state in ('proposed','accepted','rejected','postponed','completed')),
    constraint ck_intervention_usefulness check (usefulness is null or usefulness between 1 and 5)
);
create index if not exists ix_intervention_user_created
    on psychdeep_v12.intervention_events(user_id, created_at desc);

create table if not exists psychdeep_v12.knowledge_items (
    id uuid primary key default gen_random_uuid(),
    topic varchar(96) not null,
    population varchar(96) not null,
    locale varchar(16) not null default 'es-ES',
    evidence_level varchar(48) not null,
    contraindications jsonb not null default '[]'::jsonb,
    content text not null,
    content_version varchar(64) not null,
    review_due date,
    source_ref text not null,
    approved_by varchar(128),
    status varchar(24) not null default 'draft',
    created_at timestamptz not null default now(),
    constraint ck_knowledge_status check (status in ('draft','active','retired')),
    unique(topic, population, locale, content_version)
);

create table if not exists psychdeep_v12.fine_tune_runs (
    id uuid primary key default gen_random_uuid(),
    dataset_version varchar(96) not null,
    base_model_checksum varchar(128) not null,
    tokenizer_checksum varchar(128),
    code_commit varchar(64) not null,
    container_digest varchar(192),
    hyperparameters jsonb not null default '{}'::jsonb,
    artifact_checksum varchar(128),
    eval_result jsonb not null default '{}'::jsonb,
    approval_status varchar(40) not null default 'experiment',
    created_at timestamptz not null default now(),
    constraint ck_fine_tune_approval check (approval_status in ('experiment','evaluated','clinically_reviewed','approved_for_shadow','approved_for_canary','production','retired'))
);

create table if not exists psychdeep_v12.model_deployments (
    alias varchar(96) primary key,
    adapter varchar(48) not null,
    model_id varchar(192) not null,
    capabilities jsonb not null default '{}'::jsonb,
    policy_version varchar(96) not null,
    timeout_seconds integer not null default 45,
    data_handling_classification varchar(64) not null,
    base_url_ref varchar(96),
    credential_ref varchar(96),
    region varchar(64),
    status varchar(24) not null default 'disabled',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint ck_model_deployment_adapter check (adapter in ('openai_compatible','managed_cloud')),
    constraint ck_model_deployment_status check (status in ('disabled','approved','shadow','canary','production','retired')),
    constraint ck_model_deployment_timeout check (timeout_seconds between 1 and 600)
);

-- Additive compatibility columns on existing history-bearing tables.
alter table psychdeep_v12.user_consents
    add column if not exists scope jsonb not null default '{}'::jsonb,
    add column if not exists valid_until timestamptz,
    add column if not exists source varchar(32) not null default 'user';

alter table psychdeep_v12.risk_assessments
    add column if not exists rule_set_version varchar(64);
update psychdeep_v12.risk_assessments
   set rule_set_version = coalesce(rule_set_version, model_version, 'risk-engine-v1.4')
 where rule_set_version is null;
alter table psychdeep_v12.risk_assessments
    alter column rule_set_version set default 'risk-engine-v1.4',
    alter column rule_set_version set not null;

alter table psychdeep_v12.professional_alerts
    add column if not exists protocol_version varchar(64),
    add column if not exists outcome_feedback jsonb;

alter table psychdeep_v12.chat_messages
    add column if not exists conversation_id uuid,
    add column if not exists model_run_id uuid references psychdeep_v12.model_runs(id) on delete set null;
create index if not exists ix_chat_messages_conversation
    on psychdeep_v12.chat_messages(user_id, conversation_id, created_at)
    where conversation_id is not null;

-- ---------------------------------------------------------------------
-- Historical compatibility backfill. Original rows are never changed.
-- ---------------------------------------------------------------------
insert into psychdeep_v12.observations
    (user_id, source, type, value, unit, occurred_at, received_at, quality,
     legacy_source_table, legacy_source_id, legacy_source_field)
select user_id, 'self_report', 'mood', jsonb_build_object('value', mood), '0-10',
       created_at at time zone 'UTC', created_at at time zone 'UTC',
       '{"legacy_import":true}'::jsonb, 'check_ins', id, 'mood'
  from psychdeep_v12.check_ins
on conflict do nothing;

insert into psychdeep_v12.observations
    (user_id, source, type, value, unit, occurred_at, received_at, quality,
     legacy_source_table, legacy_source_id, legacy_source_field)
select user_id, 'self_report', 'craving', jsonb_build_object('value', craving), '0-10',
       created_at at time zone 'UTC', created_at at time zone 'UTC',
       '{"legacy_import":true}'::jsonb, 'check_ins', id, 'craving'
  from psychdeep_v12.check_ins
on conflict do nothing;

insert into psychdeep_v12.observations
    (user_id, source, type, value, unit, occurred_at, received_at, quality,
     legacy_source_table, legacy_source_id, legacy_source_field)
select user_id, 'self_report', 'sleep_hours', jsonb_build_object('value', sleep_hours), 'hours',
       created_at at time zone 'UTC', created_at at time zone 'UTC',
       '{"legacy_import":true}'::jsonb, 'check_ins', id, 'sleep_hours'
  from psychdeep_v12.check_ins
on conflict do nothing;

insert into psychdeep_v12.observations
    (user_id, source, type, value, unit, occurred_at, received_at, quality,
     legacy_source_table, legacy_source_id, legacy_source_field)
select user_id, 'self_report', 'self_efficacy', jsonb_build_object('value', self_efficacy), '0-10',
       created_at at time zone 'UTC', created_at at time zone 'UTC',
       '{"legacy_import":true}'::jsonb, 'check_ins', id, 'self_efficacy'
  from psychdeep_v12.check_ins
on conflict do nothing;

insert into psychdeep_v12.observations
    (user_id, source, type, value, occurred_at, received_at, quality,
     legacy_source_table, legacy_source_id, legacy_source_field)
select user_id, 'self_report', 'checkin_context', jsonb_build_object('text', notes),
       created_at at time zone 'UTC', created_at at time zone 'UTC',
       '{"legacy_import":true}'::jsonb, 'check_ins', id, 'notes'
  from psychdeep_v12.check_ins
 where notes is not null and btrim(notes) <> ''
on conflict do nothing;

insert into psychdeep_v12.observations
    (user_id, source, type, value, occurred_at, received_at, quality,
     legacy_source_table, legacy_source_id, legacy_source_field)
select user_id, 'self_report', 'diary_text', jsonb_build_object('text', content),
       created_at at time zone 'UTC', created_at at time zone 'UTC',
       '{"legacy_import":true}'::jsonb, 'diary_entries', id, 'content'
  from psychdeep_v12.diary_entries
on conflict do nothing;

insert into psychdeep_v12.baseline_versions
    (user_id, feature_key, window_start, window_end, stats, exclusions, stability,
     status, algorithm_version, legacy_baseline_id, created_at)
select user_id, null, window_start at time zone 'UTC', window_end at time zone 'UTC',
       stats::jsonb, '[]'::jsonb, 'legacy_unknown',
       case when is_active then 'active' else 'retired' end,
       'legacy-baseline-import-v1', id, created_at at time zone 'UTC'
  from psychdeep_v12.baselines
on conflict do nothing;

insert into psychdeep_v12.change_signals
    (user_id, feature, window_start, window_end, band, uncertainty, evidence_refs,
     contradictions, algorithm_version, legacy_signal_id, created_at)
select user_id, signal_type, timestamp at time zone 'UTC', timestamp at time zone 'UTC',
       case when confidence_band in ('stable','transition','unstable','insufficient_data')
            then confidence_band else 'unknown' end,
       jsonb_build_object('legacy_import', true), '[]'::jsonb, '[]'::jsonb,
       'legacy-alfa-import-v1', id, timestamp at time zone 'UTC'
  from psychdeep_v12.alfa_signals
 where signal_type <> 'linguistic_analysis'
on conflict do nothing;

insert into psychdeep_v12.inferences
    (user_id, kind, payload, uncertainty, status, algorithm_version,
     legacy_signal_id, created_at)
select user_id, signal_type, value::jsonb,
       jsonb_build_object('legacy_import', true),
       case when is_active then 'active' else 'retired' end,
       'legacy-alfa-import-v1', id, timestamp at time zone 'UTC'
  from psychdeep_v12.alfa_signals
 where signal_type = 'linguistic_analysis'
on conflict do nothing;

-- Backfill ModelRun from auditable analyzer traces without duplicating raw PHI.
insert into psychdeep_v12.model_runs
    (id, user_id, purpose, audience, deployment_alias, provider_type, model_id,
     model_version, prompt_version, policy_version, input_hash, output_schema,
     status, correlation_id, latency_ms, input_tokens, output_tokens, created_at)
select t.id, t.user_id, 'linguistic_and_psychosocial_analysis', 'system',
       'legacy-' || coalesce(t.provider, 'unknown'),
       coalesce(t.provider, 'unknown'), coalesce(t.requested_model, 'unknown'),
       t.response_model, t.prompt_version, 'legacy-policy',
       coalesce(t.prompt_sha256, repeat('0', 64)), t.schema_version,
       case when t.status in ('started','succeeded','refused','invalid_output','provider_error','timeout','configuration_error','abandoned')
            then t.status else 'provider_error' end,
       t.correlation_id, t.latency_ms, t.input_tokens, t.output_tokens,
       coalesce(t.created_at, now())
  from psychdeep_v12.agent2_analysis_traces t
on conflict (id) do nothing;

-- Canonical aliases contain only metadata and references to environment
-- variable names; no URL/token is stored in the clinical database.
insert into psychdeep_v12.model_deployments
    (alias, adapter, model_id, capabilities, policy_version, timeout_seconds,
     data_handling_classification, base_url_ref, credential_ref, region, status)
values
    ('local-tunnel', 'openai_compatible', 'configured-at-runtime',
     '{"chat":true,"structured":true}'::jsonb, 'support-policy-v1', 45,
     'clinical_data_private_tunnel', 'MODEL_LOCAL_BASE_URL', 'MODEL_LOCAL_API_KEY', null, 'approved'),
    ('cloud-tuned', 'managed_cloud', 'configured-at-runtime',
     '{"chat":true,"structured":true}'::jsonb, 'support-policy-v1', 45,
     'clinical_data_managed_private', 'MODEL_CLOUD_BASE_URL', 'MODEL_CLOUD_API_KEY', 'EU/EEE-preferred', 'disabled')
on conflict (alias) do update set
    adapter = excluded.adapter,
    capabilities = excluded.capabilities,
    policy_version = excluded.policy_version,
    timeout_seconds = excluded.timeout_seconds,
    data_handling_classification = excluded.data_handling_classification,
    base_url_ref = excluded.base_url_ref,
    credential_ref = excluded.credential_ref,
    region = excluded.region,
    updated_at = now();

-- Harden every new table identically. No anon/authenticated/service_role and
-- intentionally no psychdeep_sync grant/policy.
do $$
declare
    table_name text;
begin
    foreach table_name in array array[
        'observations','feature_definitions','feature_values','baseline_versions',
        'change_signals','model_runs','inferences','intervention_events',
        'knowledge_items','fine_tune_runs','model_deployments'
    ] loop
        execute format('alter table psychdeep_v12.%I enable row level security', table_name);
        execute format('alter table psychdeep_v12.%I force row level security', table_name);
        execute format('drop policy if exists backend_full_access on psychdeep_v12.%I', table_name);
        execute format(
            'create policy backend_full_access on psychdeep_v12.%I for all to psychdeep_backend using (true) with check (true)',
            table_name
        );
        execute format('revoke all on table psychdeep_v12.%I from public, anon, authenticated, service_role', table_name);
        if exists (select 1 from pg_roles where rolname = 'psychdeep_sync') then
            execute format('revoke all on table psychdeep_v12.%I from psychdeep_sync', table_name);
        end if;
    end loop;
end
$$;

reset role;
revoke psychdeep_backend from postgres granted by postgres;

-- Fail the transaction if a new canonical table escaped ownership/RLS or if
-- the temporary role membership was not restored.
do $$
declare
    bad_count integer;
    policy_count integer;
    sync_policy_count integer;
begin
    select count(*) into bad_count
      from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
      join pg_roles r on r.oid = c.relowner
     where n.nspname = 'psychdeep_v12'
       and c.relname = any(array[
           'observations','feature_definitions','feature_values','baseline_versions',
           'change_signals','model_runs','inferences','intervention_events',
           'knowledge_items','fine_tune_runs','model_deployments'
       ])
       and (r.rolname <> 'psychdeep_backend' or not c.relrowsecurity or not c.relforcerowsecurity);
    if bad_count <> 0 then
        raise exception 'vNext canonical table owner/RLS hardening incomplete (% tables)', bad_count;
    end if;

    select count(*) into policy_count
      from pg_policies
     where schemaname = 'psychdeep_v12'
       and tablename = any(array[
           'observations','feature_definitions','feature_values','baseline_versions',
           'change_signals','model_runs','inferences','intervention_events',
           'knowledge_items','fine_tune_runs','model_deployments'
       ])
       and policyname = 'backend_full_access'
       and 'psychdeep_backend' = any(roles);
    if policy_count <> 11 then
        raise exception 'expected 11 backend policies on vNext canonical tables, found %', policy_count;
    end if;

    select count(*) into sync_policy_count
      from pg_policies
     where schemaname = 'psychdeep_v12'
       and tablename = any(array[
           'observations','feature_definitions','feature_values','baseline_versions',
           'change_signals','model_runs','inferences','intervention_events',
           'knowledge_items','fine_tune_runs','model_deployments'
       ])
       and 'psychdeep_sync' = any(roles);
    if sync_policy_count <> 0 then
        raise exception 'vNext canonical tables must not be readable by psychdeep_sync';
    end if;
end
$$;

commit;

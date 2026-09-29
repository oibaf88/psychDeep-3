-- PsychDeep vNext — Supabase readiness check. Run this BEFORE the Render deploy.
--
-- It reproduces the production startup contract plus database hardening and
-- verifies that the retired local-sync authority can no longer authenticate or
-- reach clinical tables. Every row must read `ok`.
--
-- Read-only: it changes nothing. Safe to run against a live project.

with settings as (
    select 'psychdeep_v12'::name as target_schema
),
app_tables as (
    select relation.oid,
           relation.relname,
           pg_get_userbyid(relation.relowner) as owner,
           relation.relrowsecurity,
           relation.relforcerowsecurity
      from pg_class relation
      join pg_namespace namespace on namespace.oid = relation.relnamespace
      join settings on namespace.nspname = settings.target_schema
     where relation.relkind = 'r'
),
expected_tables(table_name) as (values
    -- Legacy history remains readable during expand-and-migrate.
    ('agent2_analysis_traces'), ('alfa_signals'), ('audit_log'), ('baselines'),
    ('chat_messages'), ('check_ins'), ('confirmed_facts'), ('diary_entries'),
    ('llm_endpoint_configs'), ('llm_usage_events'), ('notifications'),
    ('password_reset_tokens'), ('patient_professional_assignments'),
    ('patient_profiles'), ('professional_alerts'), ('psychosocial_observations'),
    ('risk_assessments'), ('safety_plans'), ('therapist_copilot_messages'),
    ('user_consents'), ('users'),
    -- Canonical vNext data plane.
    ('observations'), ('feature_definitions'), ('feature_values'),
    ('baseline_versions'), ('change_signals'), ('model_runs'), ('inferences'),
    ('intervention_events'), ('knowledge_items'), ('fine_tune_runs'),
    ('model_deployments')
),
required_columns(table_name, column_name) as (values
    ('agent2_analysis_traces', 'id'),
    ('agent2_analysis_traces', 'agent_role'),
    ('agent2_analysis_traces', 'provider_base_url'),
    ('alfa_signals', 'agent2_trace_id'),
    ('risk_assessments', 'correlation_id'),
    ('risk_assessments', 'agent2_trace_id'),
    ('risk_assessments', 'linguistic_signal_id_used'),
    ('risk_assessments', 'calculation_trace'),
    ('risk_assessments', 'rule_set_version'),
    ('therapist_copilot_messages', 'id'),
    ('psychosocial_observations', 'id'),
    ('psychosocial_observations', 'evidence_quote'),
    ('llm_endpoint_configs', 'id'),
    ('llm_endpoint_configs', 'copilot_model'),
    ('patient_profiles', 'id'),
    ('patient_profiles', 'linguistic_baseline'),
    ('users', 'first_name'),
    ('users', 'last_name'),
    ('users', 'phone'),
    ('users', 'auth_version'),
    ('users', 'updated_at'),
    ('users', 'local_llm_approved'),
    ('users', 'local_llm_approved_at'),
    ('users', 'local_llm_approved_by'),
    ('user_consents', 'scope'),
    ('user_consents', 'valid_until'),
    ('chat_messages', 'provider'),
    ('chat_messages', 'model'),
    ('chat_messages', 'provider_base_url'),
    ('chat_messages', 'model_run_id'),
    ('chat_messages', 'prompt_version'),
    ('chat_messages', 'prompt_sha256'),
    ('chat_messages', 'context_version'),
    ('chat_messages', 'context_sha256'),
    ('observations', 'id'),
    ('observations', 'legacy_source_id'),
    ('feature_definitions', 'id'),
    ('feature_values', 'id'),
    ('baseline_versions', 'id'),
    ('change_signals', 'id'),
    ('model_runs', 'id'),
    ('inferences', 'id'),
    ('intervention_events', 'id'),
    ('knowledge_items', 'id'),
    ('knowledge_items', 'objective'),
    ('knowledge_items', 'approved_at'),
    ('fine_tune_runs', 'id'),
    ('model_deployments', 'alias')
),
checks(sort_key, check_name, failures) as (
    select 1, 'schema exists',
           (select count(*) from settings
             where not exists (select 1 from pg_namespace
                                where nspname = settings.target_schema))

    union all
    select 2, 'psychdeep_backend role exists',
           (select count(*) from (select 1) as one
             where not exists (select 1 from pg_roles where rolname = 'psychdeep_backend'))

    union all
    select 3, 'all legacy and vNext application tables present',
           (select count(*) from expected_tables
             where table_name not in (select relname from app_tables))

    union all
    select 4, 'every table owned by psychdeep_backend',
           (select count(*) from app_tables where owner <> 'psychdeep_backend')

    union all
    select 5, 'every table has RLS enabled and forced',
           (select count(*) from app_tables
             where not relrowsecurity or not relforcerowsecurity)

    union all
    select 6, 'every table has the backend_full_access policy',
           (select count(*) from app_tables
             where not exists (
                 select 1 from pg_policies, settings
                  where pg_policies.schemaname = settings.target_schema
                    and pg_policies.tablename = app_tables.relname
                    and pg_policies.policyname = 'backend_full_access'
                    and 'psychdeep_backend' = any(pg_policies.roles)))

    union all
    select 7, 'no PostgREST role can read any table',
           (select count(*) from app_tables
             where has_table_privilege('anon', oid, 'SELECT')
                or has_table_privilege('authenticated', oid, 'SELECT')
                or has_table_privilege('service_role', oid, 'SELECT'))

    union all
    select 8, 'API startup schema contract satisfied',
           (select count(*) from required_columns, settings
             where not exists (
                 select 1 from pg_attribute
                  where attrelid = to_regclass(settings.target_schema || '.'
                                               || quote_ident(required_columns.table_name))
                    and attname = required_columns.column_name
                    and attnum > 0
                    and not attisdropped))

    union all
    select 9, 'postgres -> psychdeep_backend membership unwidened',
           (select count(*) from (select 1) as one
             where not coalesce((
                 select count(*) = 1
                    and bool_and(m.admin_option)
                    and not bool_or(m.inherit_option)
                    and not bool_or(m.set_option)
                   from pg_auth_members m
                  where m.roleid = to_regrole('psychdeep_backend')
                    and m.member = to_regrole('postgres')), false))

    union all
    select 10, 'no application tables left in public',
           (select count(*) from pg_class relation
              join pg_namespace namespace on namespace.oid = relation.relnamespace
             where namespace.nspname = 'public'
               and relation.relkind = 'r'
               and relation.relname in (select table_name from expected_tables))

    union all
    select 11, 'llm timeout ceiling is 5000s',
           (select count(*) from (select 1) as one
             where not exists (
                 select 1
                   from pg_constraint c
                   join pg_class relation on relation.oid = c.conrelid
                   join pg_namespace namespace on namespace.oid = relation.relnamespace
                   join settings on namespace.nspname = settings.target_schema
                  where relation.relname = 'llm_endpoint_configs'
                    and c.conname = 'ck_llm_endpoint_timeout'
                    and pg_get_constraintdef(c.oid) like '%5000%'))

    union all
    select 12, 'users email is unique ignoring case',
           (select count(*) from (select 1) as one
             where not exists (
                 select 1 from pg_indexes, settings
                  where pg_indexes.schemaname = settings.target_schema
                    and pg_indexes.tablename = 'users'
                    and pg_indexes.indexname = 'ix_users_email_lower'
                    and pg_indexes.indexdef ilike '%unique%'
                    and pg_indexes.indexdef ilike '%lower%email%'))

    union all
    select 13, 'retired psychdeep_sync cannot authenticate',
           (select count(*) from pg_roles
             where rolname = 'psychdeep_sync' and rolcanlogin)

    union all
    select 14, 'retired psychdeep_sync has no RLS policies',
           (select count(*) from pg_policies, settings
             where schemaname = settings.target_schema
               and 'psychdeep_sync' = any(roles))

    union all
    select 15, 'retired psychdeep_sync has no clinical table privileges',
           (select count(*) from app_tables
             where exists (select 1 from pg_roles where rolname = 'psychdeep_sync')
               and (has_table_privilege('psychdeep_sync', oid, 'SELECT')
                 or has_table_privilege('psychdeep_sync', oid, 'INSERT')
                 or has_table_privilege('psychdeep_sync', oid, 'UPDATE')
                 or has_table_privilege('psychdeep_sync', oid, 'DELETE')))

    union all
    select 16, 'SymmetricDS metadata schema removed',
           (select count(*) from pg_namespace where nspname = 'psychdeep_sync')

    union all
    select 17, 'knowledge registry enforces one active version per target',
           (select count(*) from (select 1) as one
             where not exists (
                 select 1 from pg_indexes, settings
                  where pg_indexes.schemaname = settings.target_schema
                    and pg_indexes.tablename = 'knowledge_items'
                    and pg_indexes.indexname = 'ux_knowledge_one_active_version'
                    and pg_indexes.indexdef ilike '%unique%'
                    and pg_indexes.indexdef ilike '%where (status%active%'))
)
select check_name,
       case when failures = 0 then 'ok' else 'FAILED' end as status,
       failures as offending_rows
  from checks
 order by sort_key;

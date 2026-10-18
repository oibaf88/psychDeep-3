-- Canonical embeddings attached to ChangeSignal (not Advisor-only, not risk).
-- Vectors are retrieval/explainability for longitudinal self-regulation.
-- They MUST NOT feed alert_level. Writer requires linguistic_analysis + consent_id.
begin;
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

create table if not exists psychdeep_v12.change_signal_embeddings (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references psychdeep_v12.users(id) on delete cascade,
    change_signal_id uuid not null references psychdeep_v12.change_signals(id) on delete cascade,
    consent_id uuid references psychdeep_v12.user_consents(id) on delete set null,
    purpose varchar(48) not null default 'linguistic_analysis',
    embedding jsonb,
    provider varchar(96) not null,
    embedding_model varchar(192) not null,
    algorithm_version varchar(64) not null,
    created_at timestamptz not null default now(),
    constraint ck_cse_purpose check (purpose = 'linguistic_analysis'),
    constraint uq_cse_signal unique (change_signal_id)
);

create index if not exists ix_cse_user_created
    on psychdeep_v12.change_signal_embeddings(user_id, created_at desc);
create index if not exists ix_cse_consent
    on psychdeep_v12.change_signal_embeddings(consent_id)
    where consent_id is not null;

alter table psychdeep_v12.change_signal_embeddings enable row level security;
alter table psychdeep_v12.change_signal_embeddings force row level security;
drop policy if exists backend_full_access on psychdeep_v12.change_signal_embeddings;
create policy backend_full_access on psychdeep_v12.change_signal_embeddings
    for all to psychdeep_backend using (true) with check (true);
revoke all on table psychdeep_v12.change_signal_embeddings from public, anon, authenticated, service_role;

reset role;
revoke psychdeep_backend from postgres granted by postgres;

do $$
declare
    owner_name text;
    rls_enabled boolean;
    rls_forced boolean;
    policy_exists boolean;
begin
    select owner_role.rolname, relation.relrowsecurity, relation.relforcerowsecurity
      into owner_name, rls_enabled, rls_forced
      from pg_class relation
      join pg_namespace namespace on namespace.oid = relation.relnamespace
      join pg_roles owner_role on owner_role.oid = relation.relowner
     where namespace.nspname = 'psychdeep_v12'
       and relation.relname = 'change_signal_embeddings';

    select exists (
        select 1 from pg_policies
         where schemaname = 'psychdeep_v12'
           and tablename = 'change_signal_embeddings'
           and policyname = 'backend_full_access'
           and 'psychdeep_backend' = any(roles)
    ) into policy_exists;

    if owner_name is distinct from 'psychdeep_backend'
       or not coalesce(rls_enabled, false)
       or not coalesce(rls_forced, false)
       or not policy_exists then
        raise exception 'change_signal_embeddings owner/RLS hardening is incomplete';
    end if;
end
$$;

commit;

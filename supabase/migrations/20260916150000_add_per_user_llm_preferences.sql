-- Each account owns its provider selection and encrypted credentials.
-- Ciphertext is encrypted in the backend using LLM_USER_CREDENTIALS_KEY,
-- which MUST NOT be stored in Supabase, GitHub or the frontend.
begin;
do $$
declare membership_is_expected boolean;
begin
    select count(*) = 1 and bool_and(m.admin_option)
       and not bool_or(m.inherit_option) and not bool_or(m.set_option)
       and bool_and(grantor.rolname = 'supabase_admin')
      into membership_is_expected
      from pg_auth_members m
      join pg_roles granted_role on granted_role.oid = m.roleid
      join pg_roles member_role on member_role.oid = m.member
      join pg_roles grantor on grantor.oid = m.grantor
     where granted_role.rolname = 'psychdeep_backend'
       and member_role.rolname = 'postgres';
    if not coalesce(membership_is_expected,false) then
        raise exception 'Unexpected backend role membership; migration stopped safely';
    end if;
end $$;
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;
create table if not exists psychdeep_v12.llm_user_preferences (
    user_id uuid primary key references psychdeep_v12.users(id) on delete cascade,
    provider varchar(32) not null default 'anthropic',
    base_url varchar(500),
    chat_model varchar(192) not null default 'claude-3-5-sonnet-20240620',
    analysis_model varchar(192) not null default 'claude-3-5-sonnet-20240620',
    copilot_model varchar(192) not null default '',
    max_tokens integer not null default 4096,
    timeout_seconds integer not null default 120,
    lm_api_key_encrypted text,
    cf_client_id_encrypted text,
    cf_client_secret_encrypted text,
    updated_at timestamptz not null default now(),
    constraint ck_llm_user_provider check (provider in ('anthropic', 'openai_compatible')),
    constraint ck_llm_user_max_tokens check (max_tokens between 256 and 32768),
    constraint ck_llm_user_timeout check (timeout_seconds between 5 and 5000)
);
alter table psychdeep_v12.llm_user_preferences enable row level security;
alter table psychdeep_v12.llm_user_preferences force row level security;
drop policy if exists backend_full_access on psychdeep_v12.llm_user_preferences;
create policy backend_full_access on psychdeep_v12.llm_user_preferences
    for all to psychdeep_backend using (true) with check (true);
revoke all on table psychdeep_v12.llm_user_preferences from public, anon, authenticated, service_role;
reset role;
revoke psychdeep_backend from postgres granted by postgres;
commit;

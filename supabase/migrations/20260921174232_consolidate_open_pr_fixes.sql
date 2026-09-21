-- Consolidate forward-only compatibility fixes from superseded PRs.
-- Existing clinical/history rows are preserved; only exact obsolete model
-- identifiers and duplicate active knowledge versions are migrated.
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
    if not coalesce(membership_is_expected, false) then
        raise exception 'Unexpected backend role membership; migration stopped safely';
    end if;
end $$;

grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

-- Canonical knowledge registry: extend the table created by the vNext
-- foundation migration. Do not create a shadow public table or Data API path.
alter table psychdeep_v12.knowledge_items
    add column if not exists objective varchar(128),
    add column if not exists approved_at timestamptz;

update psychdeep_v12.knowledge_items
   set objective = topic
 where objective is null;

alter table psychdeep_v12.knowledge_items
    alter column objective set not null;

do $$
begin
    if not exists (
        select 1 from pg_constraint
         where conname = 'ck_knowledge_nonblank'
           and conrelid = 'psychdeep_v12.knowledge_items'::regclass
    ) then
        alter table psychdeep_v12.knowledge_items
            add constraint ck_knowledge_nonblank check (
                btrim(topic) <> '' and btrim(population) <> '' and
                btrim(objective) <> '' and btrim(evidence_level) <> '' and
                btrim(content) <> '' and btrim(content_version) <> '' and
                btrim(source_ref) <> '' and char_length(content) <= 20000
            ) not valid;
    end if;
end $$;

-- Deterministically retire older active duplicates before adding the
-- single-active-version invariant.
with ranked as (
    select id,
           row_number() over (
               partition by topic, population, objective, locale
               order by created_at desc, id desc
           ) as active_rank
      from psychdeep_v12.knowledge_items
     where status = 'active'
)
update psychdeep_v12.knowledge_items item
   set status = 'retired'
  from ranked
 where item.id = ranked.id
   and ranked.active_rank > 1;

create unique index if not exists ux_knowledge_one_active_version
    on psychdeep_v12.knowledge_items(topic, population, objective, locale)
    where status = 'active';
create index if not exists ix_knowledge_targeted_retrieval
    on psychdeep_v12.knowledge_items(status, population, objective, topic, locale, review_due);

-- Agent 1 audit provenance. Null on user messages and template-only replies.
alter table psychdeep_v12.chat_messages
    add column if not exists prompt_version varchar(96),
    add column if not exists prompt_sha256 varchar(64),
    add column if not exists context_version varchar(96),
    add column if not exists context_sha256 varchar(64);

-- The N3 convergence predicate/identity changed; future assessments must be
-- distinguishable from rows generated under v1.4.
alter table psychdeep_v12.risk_assessments
    alter column rule_set_version set default 'risk-engine-v1.5';

-- Replace only known retired/invalid Anthropic identifiers. User-defined
-- compatible model selections are left untouched.
alter table psychdeep_v12.llm_user_preferences
    alter column chat_model set default 'claude-sonnet-5',
    alter column analysis_model set default 'claude-sonnet-5';

update psychdeep_v12.llm_user_preferences
   set chat_model = case
           when chat_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620') then 'claude-sonnet-5'
           else chat_model
       end,
       analysis_model = case
           when analysis_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620') then 'claude-sonnet-5'
           else analysis_model
       end,
       copilot_model = case
           when copilot_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620') then 'claude-sonnet-5'
           else copilot_model
       end,
       updated_at = now()
 where provider = 'anthropic'
   and (
       chat_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620') or
       analysis_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620') or
       copilot_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620')
   );

update psychdeep_v12.llm_endpoint_configs
   set chat_model = case
           when chat_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620') then 'claude-sonnet-5'
           else chat_model
       end,
       analysis_model = case
           when analysis_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620') then 'claude-sonnet-5'
           else analysis_model
       end,
       copilot_model = case
           when copilot_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620') then 'claude-sonnet-5'
           else copilot_model
       end
 where provider = 'anthropic'
   and (
       chat_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620') or
       analysis_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620') or
       copilot_model in ('claude-opus-5', 'claude-3-5-sonnet-20240620')
   );

-- The canonical registry stays backend-only behind FastAPI authorization.
alter table psychdeep_v12.knowledge_items enable row level security;
alter table psychdeep_v12.knowledge_items force row level security;
drop policy if exists backend_full_access on psychdeep_v12.knowledge_items;
create policy backend_full_access on psychdeep_v12.knowledge_items
    for all to psychdeep_backend using (true) with check (true);
revoke all on table psychdeep_v12.knowledge_items from public, anon, authenticated, service_role;

reset role;
revoke psychdeep_backend from postgres granted by postgres;
commit;

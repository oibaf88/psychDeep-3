-- PsychDeep vNext cutover: cloud is the only clinical source of truth.
-- Retire the old bidirectional replication authority and stop retaining model
-- credentials in the clinical configuration table. Historical config rows are
-- preserved as non-secret audit/history data.

begin;

-- Deactivate every legacy runtime endpoint and irreversibly remove any stored
-- credential. vNext runtime ignores this table and resolves approved aliases
-- from server-side environment/secret configuration.
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

update psychdeep_v12.llm_endpoint_configs
   set api_key = null,
       is_active = false,
       deactivated_at = coalesce(deactivated_at, now() at time zone 'utc')
 where api_key is not null
    or is_active = true
    or deactivated_at is null;

-- Drop every RLS policy that grants the retired sync role access. Query the
-- catalog rather than maintaining another table allowlist.
do $$
declare
    policy_row record;
begin
    if exists (select 1 from pg_roles where rolname = 'psychdeep_sync') then
        for policy_row in
            select schemaname, tablename, policyname
              from pg_policies
             where schemaname = 'psychdeep_v12'
               and 'psychdeep_sync' = any(roles)
        loop
            execute format(
                'drop policy if exists %I on %I.%I',
                policy_row.policyname,
                policy_row.schemaname,
                policy_row.tablename
            );
        end loop;

        -- Table/sequence privileges are unnecessary even with RLS removed.
        execute 'revoke all privileges on all tables in schema psychdeep_v12 from psychdeep_sync';
        execute 'revoke all privileges on all sequences in schema psychdeep_v12 from psychdeep_sync';
        execute 'revoke usage on schema psychdeep_v12 from psychdeep_sync';
    end if;
end
$$;

reset role;
revoke psychdeep_backend from postgres granted by postgres;

-- SymmetricDS metadata contains replication machinery, not authoritative
-- clinical history. Drop it after the clinical grants/policies are gone.
drop schema if exists psychdeep_sync cascade;

-- Keep the role name as an inert tombstone rather than risking DROP ROLE
-- dependency surprises in an existing Supabase project. It cannot authenticate
-- and has no schema/table privileges.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'psychdeep_sync') then
        alter role psychdeep_sync nologin noinherit connection limit 0;
    end if;
end
$$;

-- Fail closed if any replication path or runtime secret survives.
do $$
declare
    remaining_policies integer;
    remaining_keys integer;
    active_configs integer;
    sync_login boolean;
begin
    select count(*) into remaining_policies
      from pg_policies
     where schemaname = 'psychdeep_v12'
       and 'psychdeep_sync' = any(roles);
    if remaining_policies <> 0 then
        raise exception 'retired sync role still has % RLS policies', remaining_policies;
    end if;

    select count(*) into remaining_keys
      from psychdeep_v12.llm_endpoint_configs
     where api_key is not null;
    if remaining_keys <> 0 then
        raise exception 'legacy llm_endpoint_configs still contains credentials';
    end if;

    select count(*) into active_configs
      from psychdeep_v12.llm_endpoint_configs
     where is_active;
    if active_configs <> 0 then
        raise exception 'legacy runtime LLM configurations are still active';
    end if;

    select rolcanlogin into sync_login
      from pg_roles where rolname = 'psychdeep_sync';
    if coalesce(sync_login, false) then
        raise exception 'psychdeep_sync must be NOLOGIN after vNext cutover';
    end if;
end
$$;

commit;

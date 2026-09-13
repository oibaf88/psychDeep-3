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

        -- Application-table grants were issued by psychdeep_backend, so the
        -- table owner revokes them here before returning to the migration role.
        execute 'revoke all privileges on all tables in schema psychdeep_v12 from psychdeep_sync';
        execute 'revoke all privileges on all sequences in schema psychdeep_v12 from psychdeep_sync';
    end if;
end
$$;

-- Validate table contents while still SET ROLE to their owner. `postgres` in
-- the hardened Supabase role model deliberately has no direct table privilege.
do $$
declare
    remaining_keys integer;
    active_configs integer;
begin
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
end
$$;

reset role;
revoke psychdeep_backend from postgres granted by postgres;

-- Schema USAGE was granted by the migration role rather than the table owner,
-- so revoke it only after RESET ROLE. This is intentionally idempotent.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'psychdeep_sync') then
        revoke usage on schema psychdeep_v12 from psychdeep_sync;
    end if;
end
$$;

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

-- Final catalog-only checks can run as the migration role without reopening
-- access to clinical tables.
do $$
declare
    remaining_policies integer;
    sync_login boolean;
    schema_usage boolean;
begin
    select count(*) into remaining_policies
      from pg_policies
     where schemaname = 'psychdeep_v12'
       and 'psychdeep_sync' = any(roles);
    if remaining_policies <> 0 then
        raise exception 'retired sync role still has % RLS policies', remaining_policies;
    end if;

    if exists (select 1 from pg_roles where rolname = 'psychdeep_sync') then
        select rolcanlogin into sync_login
          from pg_roles where rolname = 'psychdeep_sync';
        if coalesce(sync_login, false) then
            raise exception 'psychdeep_sync must be NOLOGIN after vNext cutover';
        end if;

        select has_schema_privilege('psychdeep_sync', 'psychdeep_v12', 'USAGE') into schema_usage;
        if coalesce(schema_usage, false) then
            raise exception 'psychdeep_sync retains USAGE on psychdeep_v12';
        end if;
    end if;
end
$$;

commit;

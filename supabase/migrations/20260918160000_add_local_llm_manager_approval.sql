-- Per-account authorization to use the local LM Studio / tunnel model.
-- Clinical administrators (admin_clinical) may grant or revoke this without
-- changing roles or invalidating sessions. Default is denied.
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

alter table psychdeep_v12.users
    add column if not exists local_llm_approved boolean not null default false,
    add column if not exists local_llm_approved_at timestamptz,
    add column if not exists local_llm_approved_by uuid references psychdeep_v12.users(id) on delete set null;

create index if not exists ix_users_local_llm_approved
    on psychdeep_v12.users (local_llm_approved)
    where local_llm_approved;

reset role;
revoke psychdeep_backend from postgres granted by postgres;
commit;

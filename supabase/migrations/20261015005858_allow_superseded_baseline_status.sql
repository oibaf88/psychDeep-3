-- Allow canonical analytics to retire prior algorithm versions without failing
-- the refresh transaction. Run as the backend owner so it works after RLS hardening.
begin;
grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

alter table psychdeep_v12.baseline_versions
    drop constraint if exists ck_baseline_version_status;

alter table psychdeep_v12.baseline_versions
    add constraint ck_baseline_version_status
    check (status in ('provisional', 'active', 'frozen', 'retired', 'superseded'));

reset role;
revoke psychdeep_backend from postgres granted by postgres;

commit;

-- Allow canonical analytics to retire prior algorithm versions without failing
-- the refresh transaction. The v3 pipeline explicitly marks v1/v2 rows superseded.
begin;

alter table psychdeep_v12.baseline_versions
    drop constraint if exists ck_baseline_version_status;

alter table psychdeep_v12.baseline_versions
    add constraint ck_baseline_version_status
    check (status in ('provisional', 'active', 'frozen', 'retired', 'superseded'));

commit;

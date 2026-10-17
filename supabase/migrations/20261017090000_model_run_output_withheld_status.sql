-- G3 output validation: record on the canonical ModelRun when a validated
-- conversational reply (Agent 1 patient chat, Agent 3 professional copilot)
-- was withheld by deterministic output validation, so model governance can
-- count withheld outputs.
--
-- Additive only: two new nullable columns and one new allowed status value
-- ('output_withheld'). The status check is widened to a strict superset of
-- the previous list, so every existing row stays valid. No rows are changed,
-- no columns are dropped or renamed. These columns hold the validator
-- version and rule codes only, never patient or model text.
begin;

grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

alter table psychdeep_v12.model_runs
    add column if not exists output_validator_version varchar(64);
alter table psychdeep_v12.model_runs
    add column if not exists output_violation_codes jsonb;

alter table psychdeep_v12.model_runs
    drop constraint if exists ck_model_run_status;
alter table psychdeep_v12.model_runs
    add constraint ck_model_run_status
    check (status in ('started','succeeded','refused','invalid_output','provider_error','timeout',
                      'configuration_error','unavailable','abandoned','output_withheld'));

alter table psychdeep_v12.model_runs
    drop constraint if exists ck_model_run_violation_codes;
alter table psychdeep_v12.model_runs
    add constraint ck_model_run_violation_codes
    check (output_violation_codes is null or jsonb_typeof(output_violation_codes) = 'array');

reset role;
do $$
begin
    revoke psychdeep_backend from postgres granted by postgres;
exception
    when others then
        null;
end $$;

commit;

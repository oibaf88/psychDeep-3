-- Cover vNext foreign keys used by deletes/joins. Additive and idempotent.
-- Supabase's performance advisor flags these when the referencing columns lack
-- indexes; the migration changes no clinical data or authorization behavior.

begin;

grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

create index if not exists ix_observations_consent_id
    on psychdeep_v12.observations(consent_id)
    where consent_id is not null;

create index if not exists ix_change_signals_baseline_version_id
    on psychdeep_v12.change_signals(baseline_version_id)
    where baseline_version_id is not null;

create index if not exists ix_inferences_model_run_id
    on psychdeep_v12.inferences(model_run_id)
    where model_run_id is not null;

create index if not exists ix_chat_messages_model_run_id
    on psychdeep_v12.chat_messages(model_run_id)
    where model_run_id is not null;

reset role;
revoke psychdeep_backend from postgres granted by postgres;

commit;

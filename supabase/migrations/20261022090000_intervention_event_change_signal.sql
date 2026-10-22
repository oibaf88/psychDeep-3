-- G4 intervention feedback: an InterventionEvent can now cite the patient's
-- own ChangeSignal that triggered the suggested action (Hoy accept / postpone /
-- usefulness), so usefulness can be read back against the change that
-- prompted it. It is a link for longitudinal learning only: it is not a risk
-- input and it never changes a ChangeSignal, RiskAssessment or alert level.
--
-- Additive only: one new nullable column with a foreign key that sets NULL if
-- the signal is ever removed, plus an index. No rows are changed, no defaults
-- are set, nothing is dropped or renamed. Rows written before this migration
-- stay NULL and are not back-linked.
begin;

grant psychdeep_backend to postgres with set true;
set local role psychdeep_backend;

alter table psychdeep_v12.intervention_events
    add column if not exists change_signal_id uuid
        references psychdeep_v12.change_signals(id) on delete set null;

create index if not exists ix_intervention_events_change_signal
    on psychdeep_v12.intervention_events(change_signal_id);

reset role;
do $$
begin
    revoke psychdeep_backend from postgres granted by postgres;
exception
    when others then
        null;
end $$;

commit;

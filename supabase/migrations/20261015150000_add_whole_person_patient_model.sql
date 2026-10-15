-- Compatibility shim: this migration was applied in production as version 20261015111831_add_whole_person_patient_model.
-- The earlier proposed timestamp remains as a no-op so repositories that already saw it can upgrade safely.
begin;
commit;

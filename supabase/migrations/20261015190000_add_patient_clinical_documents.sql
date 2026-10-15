-- Compatibility shim: this migration was applied in production as version 20261015111859_add_patient_clinical_documents.
-- The earlier proposed timestamp remains as a no-op so repositories that already saw it can upgrade safely.
begin;
commit;

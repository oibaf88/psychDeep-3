-- Compatibility shim: this migration was applied in production as version 20261015111846_add_longitudinal_fulltext_indexes.
-- The earlier proposed timestamp remains as a no-op so repositories that already saw it can upgrade safely.
begin;
commit;

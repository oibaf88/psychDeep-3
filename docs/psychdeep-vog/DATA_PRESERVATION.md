# Clinical data preservation and compatibility plan

## Protected assets
- Existing patient/source rows and stable IDs.
- Chat and diary history, check-ins, confirmed facts, psychosocial observations and professional annotations.
- Consent history, assignment/authorisation records and audit trails.
- Model runs, failed/succeeded analysis runs, job history, dead-letter rows, source references and previous patient-model versions.
- Existing schema/migration history, backups and deployment configuration.

## Prohibited operations
No production table drops, truncation, destructive backfills, bulk overwrites, reset/reseed, schema replacement, database URL switch, deletion of failed jobs, or mass replay. Do not create a replacement production database as a debugging shortcut.

## Compatibility rules
- Product branding may change to psychDeep-vOG; internal identifiers remain stable until reviewed.
- Keep `psychdeep_v12`, service IDs/URLs, migration names and historical refs as compatibility identifiers.
- Add columns/tables only through additive, reversible migrations after tests and review.
- Prefer new version rows and supersession markers over update-in-place for derived memory.
- Preserve failed jobs and their error metadata as incident evidence.

## Before any future migration
1. Confirm a recoverable backup/PITR posture and record the recovery point.
2. Capture counts and time ranges per protected table; capture constraints/indexes, migration versions and schema dump.
3. Produce a dry-run migration and rollback plan.
4. Compare source IDs and row counts before/after; compute deterministic checksums for stable, non-PII columns where practical.
5. Verify FK integrity, source-ref resolution, consent/assignment constraints, and historical version availability.
6. Run representative clinical-validation fixtures and API/UI smoke tests.
7. Obtain explicit approval before production execution.
8. After execution, compare counts/checksums, inspect errors, and keep rollback available.

## Recovery
Never “fix” a failed model by deleting source or failed analysis rows. Correct the code, validate in tests/staging, then replay only selected jobs through an audited, idempotent operator workflow. Preserve original job ID/history and link any replay to the incident/correlation ID.

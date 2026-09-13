# PsychDeep vNext operational runbooks

These runbooks are deliberately provider-neutral. Clinical safety must not require the generative model.

## DB outage

1. Confirm `/api/v1/health` database failure and Supabase project status.
2. Stop nonessential writes/jobs; do not redirect clinical traffic to a local database.
3. Keep static crisis/help content available from the web bundle where possible.
4. Restore Supabase/service connectivity using the provider recovery path.
5. Verify row counts/audit continuity after recovery.
6. Record incident, start/end, affected functions and any lost requests.

## Migration failure

1. Stop the application release; do not partially roll forward code that requires missing columns.
2. Preserve logs and migration version; do not hand-edit clinical rows to “make it work”.
3. If the migration transaction rolled back, fix migration + CI and reapply.
4. If a non-transactional side effect occurred, compare backup/row counts and obtain Data + QA sign-off.
5. Prefer app rollback for expand-only vNext changes.

## Local model tunnel down

1. Confirm core API/data/safety health first.
2. Check `/api/v1/model/deployments/status`; expected model state is unavailable/degraded.
3. Verify no silent provider switch occurred.
4. On the trusted model host, check model server, local token and named tunnel/Access client.
5. Restore inference only; do not expose a router port or product/database service.
6. Confirm model health, then one synthetic non-clinical inference.

## Managed model endpoint failure

1. Keep selected deployment alias unchanged unless an approved rollback is explicitly executed.
2. Core deterministic functions remain available; return structured/static support for model-dependent flows.
3. Inspect provider status/latency without logging prompt bodies.
4. Roll model alias/version back only through Ops/ML release procedure.

## Auth outage / mass session invalidation

1. Confirm whether failure is identity/session validation vs database/API.
2. Do not weaken authorization/RLS to restore access.
3. Preserve crisis/help resources that do not require clinical record access.
4. Restore identity/session service; test patient, therapist, supervisor and admin-clinical negative paths.

## Professional alert delivery failure

1. RiskAssessment remains authoritative even if notification delivery fails.
2. Record delivery failure separately; do not downgrade/delete the assessment.
3. Retry only through approved notification route and dedupe rules.
4. Surface pending/failed state to authorised professionals/operators.

## Secret rotation

1. Create a new server-side secret/token; never write it to DB, Git, issue or browser config.
2. Update Render/tunnel secret store with overlapping validity if possible.
3. Verify synthetic model health/call.
4. Revoke old secret.
5. Audit only reference/version/time, not the secret value.

## Supabase restore

1. Identify restore point and expected RPO/RTO.
2. Restore to the authorised cloud environment, not a laptop clinical DB.
3. Verify migrations, ownership, FORCE RLS, backend policy and row-count/control samples.
4. Verify risk/fact/audit lineage before reopening writes.

## Security incident / suspected PHI exposure

1. Contain affected endpoint/credential without deleting evidence.
2. Rotate exposed secrets and invalidate sessions as appropriate.
3. Determine data classes, time window and actors from minimised audit/infrastructure logs.
4. Do not copy raw PHI into tickets/chat during incident handling.
5. Follow applicable breach/legal process and document decisions.

## RAG/content incident

1. Retire affected `KnowledgeItem` version; never edit historical provenance silently.
2. Ensure deterministic crisis resources remain available independently.
3. Identify ModelRuns that referenced the affected content version.
4. Publish reviewed replacement and run safety/content regression suite before activation.

## Release rollback

1. Revert/redeploy the last known-good application commit.
2. Keep additive canonical DB tables in place unless a separately approved destructive rollback exists.
3. Roll back model alias/version independently if it caused the incident.
4. Never restore the retired local clinical database/SymmetricDS design as an emergency shortcut.
5. Re-run health, auth-negative, safety-offline and data-integrity smoke tests.

# Memory pipeline operations runbook

## First response to a failure
1. Record incident time range, service/deployment commit, job type, correlation ID, job ID and aggregate status counts.
2. Inspect safe logs for category and file/line/function frames. Do not copy clinical text, prompts, provider payloads, tokens or secrets into tickets.
3. Determine whether the error is input/schema, provider, source-reference, DB/transaction, consent or worker-state related.
4. Preserve the failed analysis run and job row. Do not mass-requeue or delete dead letters.
5. Reproduce with a synthetic fixture and the same prompt/schema version in a non-production test environment.

## Safe telemetry
Allowed: exception class/category, source-code location, correlation ID, job ID, job type, attempt number, elapsed time, schema/prompt version, status transition and aggregate counts.
Forbidden: patient text, diary/chat excerpts, generated clinical text, model prompts/responses, authentication headers, provider keys and raw exception messages unless separately reviewed and redacted.

## Retry and replay
- Normal retries are bounded and idempotent.
- A dead-letter replay is an explicit operator action after root cause is fixed and a dry-run proves eligibility.
- Keep original job/analysis rows; link replay to incident and original IDs.
- Recheck current consent immediately before any model call and before publication.
- Never replace the active model with a partial candidate.
- Stop replay if source coverage, schema, consent or persistence validation fails.

## Release checklist
- CI green and regression test reproduces the previously failing case before the fix and passes after it.
- DB schema is unchanged unless an additive reviewed migration is explicitly included.
- No data deletion/backfill; old model versions remain queryable.
- API contract tests and therapist/patient UI tests pass.
- Authorisation negative tests pass.
- Staging smoke test confirms ready/processing/partial/failed/consent/no-evidence states.
- Product owner approves the exact PR before merge and the deployment before production rollout.

## Rollback
Rollback application code to the prior known-good commit. Do not roll back by dropping tables or deleting derived history. If a migration was approved, use its tested additive compatibility/rollback procedure and preserve source and audit rows.

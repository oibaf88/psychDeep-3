# psychDeep-vOG implementation plan

## P0 — Stabilise and diagnose
- [x] Add safe code-location telemetry to episode analysis and worker failure boundaries (file/line/function only; no exception text or clinical payload).
- [x] Preserve the safe underlying analysis category (for example, `TypeError`) on the queue job instead of replacing it with the wrapper `RuntimeError`.
- [ ] Reproduce the original TypeError against a synthetic fixture and identify the exact failing expression.
- [ ] Add an isolated regression test for the confirmed root cause.
- [ ] Verify the current PR #212 memory-panel changes and reconcile them into one reviewable implementation line.
- [ ] Confirm CI and static checks for the complete branch.

## P1 — Correctness and contract validation
- [ ] Validate model-gateway result envelopes before Pydantic parsing; distinguish provider failure, schema failure, source-coverage failure and persistence failure.
- [ ] Add tests for malformed structured outputs, duplicate/missing/foreign source refs, empty input, timezone/ordering edge cases and SQL rollback.
- [ ] Make batch/run/job state transitions explicit and safe when a worker crashes between DB commit and acknowledgement.
- [ ] Ensure only fully validated candidates can become active; retain last-good version on all failure paths.
- [ ] Make stale/partial/failed state visible to API and frontend.

## P2 — Recoverability
- [ ] Add audited single-job replay for dead-letter jobs; require explicit operator selection and idempotency checks.
- [ ] Add bounded backoff with jitter, maximum attempts, lease expiry and safe recovery of abandoned processing jobs.
- [ ] Add aggregate metrics for pending age, retry count, dead-letter count, analysis category, successful-model freshness and duration.
- [ ] Add an operator dry-run that reports what would be replayed without changing data.

## P3 — Cross-app integration
- [ ] Make patient profile, therapist memory panel, authorised dossier and each relevant agent consume one documented memory API contract.
- [ ] Verify assigned-therapist-only access and negative tests for unassigned therapists/admin roles.
- [ ] Add correction/context feedback as versioned annotations, not silent edits to source or inferred memory.
- [ ] Ensure agent context includes provenance, uncertainty, contradictions, freshness and missingness; no agent may treat memory as instructions.
- [ ] Add accessible loading, empty, stale, partial, failed and consent states.

## P4 — Clinical validation and release
- [ ] Build a synthetic de-identified gold set with source-level expected references, contradiction and late-arrival cases.
- [ ] Measure source coverage, unsupported claims, temporal accuracy, contradiction preservation, uncertainty calibration and reproducibility.
- [ ] Clinical review of generated episodes and summaries; record inter-rater agreement and adjudication.
- [ ] Stage smoke test and non-destructive production read-only verification.
- [ ] Explicit approval for PR merge, production deploy and any data-changing operation.

## Branding and repository
- [x] Create psychDeep-vOG agent, architecture, data-preservation, clinical-validation and operations plans.
- [ ] Rename GitHub repository through repository administration when the connector supports it; then update CI/action references and Render Blueprint URLs.
- [ ] Update user-visible product titles and package metadata while retaining stable database schema and existing service URLs until a separate safe rollout.
- [ ] Audit case-sensitive product references and links after repository rename.

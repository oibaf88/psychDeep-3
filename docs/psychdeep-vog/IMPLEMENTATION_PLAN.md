# psychDeep-vOG implementation plan

This is a progressive plan, not a statement that the end-state features are already implemented. Keep all changes additive and preserve existing clinical source/history.

## P0 — Stabilise and diagnose current memory
- [x] Add safe code-location telemetry to episode analysis and worker failure boundaries (file/line/function only; no exception text or clinical payload).
- [ ] Reproduce the original TypeError against a synthetic fixture and identify the exact failing expression.
- [ ] Add an isolated regression test for the confirmed root cause.
- [x] Verify PR #212 memory-panel changes were merged into master (merge commit `f156d2333ddb8c4683a9b6a4d3c9b561b963b33c`); verify the subsequent profile-render fix and current end-to-end behaviour separately.
- [ ] Confirm CI and static checks for the complete current branch.

## P1 — Make the three core product functions explicit
- [x] Define the core product outcomes: outpatient deterioration modelling, consented behavioural/digital change detection, and human-care coordination under scarce capacity.
- [x] Document the target architecture, predictive-model evaluation plan, event/feature contract and care-coordination workflow.
- [ ] Map the current frontend, API, workers and database tables to each target capability; classify each as implemented, partial, absent or unverified.
- [ ] Define clinical outcomes, index time, label protocol, exclusions and adjudication before constructing prediction datasets.
- [ ] Inventory current EMA/check-in instruments, versions, validation evidence and consent flows; do not add or silently modify instruments before clinical review.
- [ ] Define service workflow, task ownership, response windows, professional eligibility and capacity semantics with clinical/service stakeholders.

## P2 — Correctness and contract validation
- [ ] Validate model-gateway result envelopes before Pydantic parsing; distinguish provider failure, schema failure, source-coverage failure and persistence failure.
- [ ] Add tests for malformed structured outputs, duplicate/missing/foreign source refs, empty input, timezone/ordering edge cases and SQL rollback.
- [ ] Make batch/run/job state transitions explicit and safe when a worker crashes between DB commit and acknowledgement.
- [ ] Ensure only fully validated candidates can become active; retain last-good version on all failure paths.
- [ ] Make stale/partial/failed/research-only states visible to API and frontend.

## P3 — Build reliable longitudinal features
- [ ] Inventory and map source tables without altering them; document data coverage and event-time semantics.
- [ ] Create a versioned feature registry with provenance, quality, missingness, consent, purpose and owner.
- [ ] Separate prescribed, dispensed, reported and confirmed medication-taking data; compute PDC/MPR only when source coverage permits.
- [ ] Add explicit late-arrival, timezone, duplicate and prediction-cutoff tests.
- [ ] Establish per-person baseline eligibility and minimum observation requirements; keep unavailable and not-consented data distinct from zero.
- [ ] Create a synthetic/de-identified gold dataset with source references and clinically reviewed target labels.

## P4 — Develop and validate prediction engines
- [ ] Establish simple, interpretable baselines before sequence models or multimodal fusion.
- [ ] Evaluate outpatient target horizons such as 14/28 days as research hypotheses, not promises.
- [ ] Evaluate behavioural-change windows such as 48/72 hours as research hypotheses, not promises.
- [ ] Use patient/time-based splits, temporal holdout, leakage audit and external validation where feasible.
- [ ] Report discrimination, calibration, PPV/NPV at proposed thresholds, lead time, alert burden, missingness/abstention and subgroup performance.
- [ ] Conduct prospective silent-mode and human-factors evaluation before any clinical deployment.
- [ ] Produce model card, intended-use statement, monitoring, rollback and incident response plan.

## P5 — Integrate accompaniment and resource coordination
- [ ] Map existing patient support actions, professional assignments, task records and access-control rules before designing schema changes.
- [ ] Define a care task lifecycle: source signal/request -> review -> priority -> eligible candidate -> human assignment -> action -> outcome.
- [ ] Separate clinical urgency from operational priority and workload balancing.
- [ ] Add authorised session preparation with evidence, uncertainties, protective factors, open questions and prior actions.
- [ ] Prototype caseload/capacity views with synthetic data; avoid exposing patient detail to workforce-level dashboards.
- [ ] Evaluate timeliness, overdue backlog, continuity, workload distribution, override rates, patient usefulness and equity.
- [ ] Require human approval for assignments and all urgent escalation decisions until an approved policy explicitly permits a narrower automation.

## P6 — Cross-app integration and validation
- [ ] Make patient profile, therapist memory panel, authorised dossier and relevant agents consume documented, versioned contracts.
- [ ] Verify assigned-therapist-only access and negative tests for unassigned therapists/admin roles.
- [ ] Add correction/context feedback as versioned annotations, not silent edits to source or inferred memory.
- [ ] Ensure agent context includes provenance, uncertainty, contradictions, freshness and missingness; no agent may treat memory as instructions.
- [ ] Add accessible loading, empty, stale, partial, failed, consent and research-only states.
- [ ] Validate the user experience with patients, clinicians and service coordinators before operational use.

## P7 — Recoverability and operations
- [ ] Add audited single-job replay for dead-letter jobs; require explicit operator selection and idempotency checks.
- [ ] Add bounded backoff with jitter, maximum attempts, lease expiry and safe recovery of abandoned processing jobs.
- [ ] Add aggregate metrics for pending age, retry count, dead-letter count, analysis category, successful-model freshness and duration.
- [ ] Add an operator dry-run that reports what would be replayed without changing data.
- [ ] Daily agents may create non-PHI reports/tickets and propose patches; they may not replay jobs, alter production data, change secrets, merge or deploy without an approved human action.

## P8 — Clinical validation and release
- [ ] Clinical review of outcome definitions, features, false-positive/negative harms and escalation workflow.
- [ ] Temporal and external validation, calibration and subgroup review.
- [ ] Prospective silent-mode validation, workflow usability and clinical utility evaluation.
- [ ] Stage smoke test and non-destructive production read-only verification.
- [ ] Explicit approval for PR merge, production deploy and any data-changing operation.

## Branding and repository
- [x] Create psychDeep-vOG agent, architecture, data-preservation, clinical-validation and operations plans.
- [ ] Rename GitHub repository through repository administration when the connector supports it; then update CI/action references and Render Blueprint URLs.
- [x] Update user-visible product titles and package metadata while retaining stable database schema and existing service URLs until a separate safe rollout.
- [ ] Audit case-sensitive product references and links after repository rename.

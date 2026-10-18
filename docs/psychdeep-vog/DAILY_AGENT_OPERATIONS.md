# Daily agent and bot operating plan

## Daily cadence
One daily orchestrator produces a compact engineering report from CI and aggregate operational telemetry. More frequent checks may run on CI/deployment events, but no agent should poll production in a tight loop.

## Daily checks
- CI status, changed files, open PRs, dependency/security alerts.
- API/frontend build status and contract-test status.
- Counts by job status/category, retry/dead-letter counts and oldest queued/processing job.
- Timestamp/age of last successful whole-person model version; count of patients with no successful version (aggregate only).
- Frequency of episode TypeError and worker RuntimeError categories, with safe code-location frames.
- Stale/partial/failure UI contract coverage and therapist assignment authorization tests.
- Migration drift and backup/PITR posture, read-only only.
- Open clinical validation gates and unresolved decisions.
- Predictive research gates: data dictionary/target definition/splits/benchmark report, model lifecycle state, calibration, event coverage, false-alert burden and consent/temporal-leakage tests.
- Care coordination: aggregate queue age, tasks waiting, overdue actions, load distribution and access-control test status. Never expose identifiable patient/task details in routine bot output.

## Output format
1. Summary and confidence.
2. New regressions since prior run.
3. Exact code locations and PR/commit references.
4. Risk to data integrity, consent, privacy and clinical interpretation.
5. Recommended smallest next change with acceptance tests.
6. Progress against predictive model research: feature availability, target/label readiness, benchmark and validation gates.
7. Progress against resource allocation: task workflow, capacity data, workload equity and audit gates.
8. Blockers requiring owner/clinical/legal approval.

## Agent permissions
- Read-only production inspection by default.
- May open a branch, edit code/docs and create a draft PR.
- May not read/export patient text for routine monitoring.
- May not modify production DB, consent, secrets, service environment, deployment, schema or dead-letter state.
- May not merge/deploy or replay jobs without explicit approval.
- Do not activate a research model, retune a threshold on test outcomes, or expose predictions to patient/professional UI without formal gates.
- All changes must include a short audit trail, tests and rollback notes.

## Suggested automated roles
- **CI guardian:** tests, typing, dependency and contract drift.
- **Memory pipeline observer:** aggregate job/model freshness metrics and safe stack locations.
- **Data-integrity auditor:** counts, constraints, foreign-key/source-reference checks (read-only).
- **Clinical-validation coordinator:** test-set coverage, adjudication status and review gates; no patient-level interpretation without authorised workflow.
- **Predictive-model research coordinator:** verifies feature/target contract, temporal split/leakage checks, locked-test version, calibration, fairness and shadow status; cannot promote models.
- **Care-capacity analyst:** aggregate caseload/task due dates, staff availability/competence coverage and workload equity; recommends human review, cannot autonomously assign or deny care.
- **Release planner:** PR status, migration/deploy plan and rollback checklist.

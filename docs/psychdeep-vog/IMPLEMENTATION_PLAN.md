# psychDeep-vOG implementation plan

## P0 — Preserve and diagnose the running pilot
- [x] Safe code-location telemetry at longitudinal-analysis and worker failure boundaries (file/line/function only; no exception text or clinical payload).
- [x] Defensive frontend rendering of longitudinal profile values and memory view compatibility fixes; PR #212 and #214 merged.
- [ ] Reproduce the memory-pipeline TypeError on synthetic fixtures and identify its exact failing expression.
- [ ] Add an isolated root-cause regression test and verify the actual deployed end-to-end memory flow.
- [ ] Verify status/CI of the post-merge mainline and reconcile any stale branches.

## P1 — Agree the scientific and clinical question
- [ ] Define the primary prediction target with clinical governance: event definition, index time, observation/censoring rules, 7/14/28-day or other horizon, and permitted action.
- [ ] Run a read-only aggregate dataset audit; confirm availability, completeness, frequency, follow-up and event counts by outcome without exporting patient text.
- [ ] Complete the feature dictionary in `FEATURE_DATA_DICTIONARY_TEMPLATE.csv` with actual source columns, event/recording times, units, provenance and consent scope.
- [ ] Review and approve the proposed research architecture in `PREDICTIVE_MODEL_RESEARCH_AND_TARGET_ARCHITECTURE.md` and ADR-0003.
- [ ] Obtain DPO/legal/clinical review of intended purpose, GDPR lawful basis/special-category condition, DPIA need, MDR Rule 11, AI Act and modality-specific consent.

## P2 — Create a reproducible read-only research dataset
- [ ] Implement a feature adapter that reads existing source records without altering them and versions the source watermark, contract and transformations.
- [ ] Add checks for temporal leakage, duplicate events, timezone/late-arriving data, scale changes, missingness and consent revocation.
- [ ] Implement patient-level plus temporal splits; lock a future temporal test set before model comparison.
- [ ] Store only de-identified/synthetic fixtures in CI and avoid patient text in logs or workflow artifacts.
- [ ] Document FHIR-compatible mappings where useful, keeping original source values/IDs intact and making no schema replacement necessary.

## P3 — Benchmark the deep-learning candidates and simple controls
- [ ] Predeclare a calibrated logistic/survival baseline and current-process baseline.
- [ ] Test RETAIN or GRU-D/GRU with explicit time deltas and missingness.
- [ ] Test a compact time-aware Transformer; compare late fusion only after validating each modality separately.
- [ ] Consider BEHRT/Hi-BEHRT-style transfer only after confirming dataset scale, vocabularies, licensing, language, compute and target transferability.
- [ ] For behavioral-change prediction, compare structured EMA-only, consented text-only and fused model; do not enable passive sensing by default.
- [ ] Report AUPRC, AUROC, Brier score, calibration slope/intercept, clinically predeclared sensitivity/PPV, false alerts per person-month, lead time, subgroup results and patient-clustered confidence intervals.
- [ ] Record failure/abstention for insufficient data, not a fabricated probability of zero.

## P4 — Versioned shadow evaluation
- [ ] Persist model artifacts and metadata under a research/shadow lifecycle separate from `RiskAssessment` and the LLM memory model.
- [ ] Run retrospective locked-test and then prospective shadow mode where outputs do not influence care.
- [ ] Review false positives, false negatives, useful lead time, alert burden, fairness, drift and clinician/patient acceptability.
- [ ] Prohibit automatic retraining, threshold tuning against the locked test set, and silent model promotion.

## P5 — Human care coordination and capacity
- [ ] Audit existing assignments, professional alerts, notifications and task abstractions before adding new schema.
- [ ] Define a human-owned work queue with priority rationale/evidence, due date/SLA, competencies, availability, continuity, caseload and audited feedback.
- [ ] Keep deterministic safety escalation independent; no automatic contact, restrictive action, denial of care or allocation based solely on unvalidated score.
- [ ] Measure time to review, overdue work, workload equity, actionable-alert rate and patient/clinician experience.
- [ ] Add negative authorization tests for unassigned clinicians and non-clinical admins.

## P6 — Infrastructure and deployment gates
- [x] Confirm Supabase `psychdeep_v12` is active and contains the pilot's canonical tables and longitudinal memory entities; confirm Render API/web services remain linked to the existing repository.
- [x] Confirm Supabase has a security advisory for `vector` in `public` and performance advisories for missing covering indexes; no production remediation performed.
- [ ] Review and remediate advisory findings in a test/staging-first, additive and reversible workflow.
- [ ] Verify effective backups/PITR, restore drill, log retention, RPO/RTO, privacy/subprocessor terms and security controls for the contracted plans.
- [ ] Keep Supabase as the clinical source of truth and Render hosting in the first implementation stage.
- [ ] Evaluate Modal only for isolated batch/GPU compute after reviewing EU routing, ingress, logs, volumes/snapshots, DPA, sub-processors/transfers and total cost.
- [ ] Do not change source DB, service URLs, runtime secrets, deploy state or replay production jobs as a side effect of this plan.

## P7 — Release to assisted care
- [ ] Complete intended-purpose and regulatory assessment, clinical safety case and validation protocol.
- [ ] Approve model-release thresholds before observing final test performance.
- [ ] Confirm temporal/external validation, calibration, clinical utility, acceptable alert load, human factors, fairness and rollback.
- [ ] Obtain explicit product-owner/clinical approval for production code merge and rollout.
- [ ] Preserve all source and historical derived data; new predictions are additive versioned records.

## Branding/repository
- [x] Documentation identity set to psychDeep-vOG without changing database schema or service URLs.
- [ ] Rename GitHub repository through repository administration when available; only then update Render repo bindings in a controlled rollout.
- [ ] Audit case-sensitive product references and links after any actual repository rename.

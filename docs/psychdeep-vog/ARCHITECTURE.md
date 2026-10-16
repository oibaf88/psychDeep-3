# psychDeep-vOG architecture

## System of record
The existing Supabase PostgreSQL project and `psychdeep_v12` schema remain the sole production clinical source of truth. Render hosts the web frontend and API/worker. The optional ML-compute provider is replaceable and cannot hold the only copy of clinical records. Model providers sit behind the existing provider-neutral Model Gateway. A provider outage must not disable source storage, deterministic safety processing or access to the last successful memory version.

## Product planes — keep the semantics separate

1. **Canonical clinical/source plane:** chat/diary/check-ins, explicit observations and facts, consent/assignment/audit, and other source records. Source timestamps/provenance remain authoritative.
2. **Longitudinal memory plane:** LLM-supported extraction/episode/digest/patient formulation. Source-linked, provisional and versioned. It is not a relapse predictor.
3. **Predictive research plane A — outpatient deterioration:** candidate temporal deep-learning model over verified structured/semi-structured clinical events. Output is research-only until target-specific clinical validation and legal release.
4. **Predictive research plane B — digital/behavioral change:** individual-level temporal models over consented EMA/check-ins/diary first, using irregular-time embeddings, personal baselines and explicit missingness. Passive sensors are out of initial scope.
5. **Deterministic safety plane:** existing risk/crisis engine remains independent of LLM and experimental model results.
6. **Care-operations plane:** human-owned review tasks, allocation constraints, professional competence/availability, due dates, feedback and audit. Predictions inform a reviewable workflow only after an approved release.
7. **Compute plane:** Render workers for light orchestration initially; optional Modal execution later for controlled CPU/GPU jobs. Never move the clinical source-of-truth there.

## Logical flow
```text
Existing canonical sources in Supabase
  |-- check-ins / EMA / diary / observation / explicit clinical sources
  |-- source time, recorded time, provenance and purpose-specific consent
  v
Read-only feature adapter + validated source snapshot
  |-- verified available fields only
  |-- event-time cutoff, irregular time deltas, missingness masks
  v
Separate research model pipelines
  |-- A: EHR/clinical temporal prediction (if source data and target exist)
  |-- B: individualized EMA/text time-series deviation
  v
Model registry + evaluation metadata (research/shadow/approved)
  |-- outcome/horizon + model and feature versions
  |-- calibration, uncertainty, coverage, source watermark
  |-- AUPRC/AUROC/calibration/utility/fairness/false alert burden
  v
Approved output contract (initially shadow only)
  v
Human review queue / session preparation / care coordination
  |-- assignment and competence checks, workload/capacity, audited actions
  v
Feedback and prospective validation
```

## Predictive model policy
- Define the target before the model; every prediction requires an index time, horizon, version, source watermark, available modalities, missingness/coverage and validation state.
- Explore calibrated statistical baselines, RETAIN/GRU-D/GRU temporal models, compact time-aware Transformers, then BEHRT/Hi-BEHRT-style transfer if scale/vocabulary/licensing justify it.
- For EMA/digital change, compare structured EMA-only, consented text-only and late-fusion models. No passive GPS, keyboard content, contacts or third-party messages by default.
- Any reported horizon such as 14–28 days or 48–72 hours is a hypothesis for evaluation, never product promise before validation.
- Research output cannot modify `RiskAssessment.alert_level`, clinical diagnoses, prescriptions or automatic escalation. Insufficient data means abstention, not normality.
- Do not let LLM-generated memory, unvalidated inferred diagnoses or future events leak into training labels/features.
- Clinical review, locked temporal test, calibration, utility, subgroup performance, data-protection assessment and intended-purpose/regulatory review precede visible assisted-care use.

## Memory layers
1. **Source records:** immutable from the memory pipeline's perspective; normal user/clinician correction flows retain their own audit history.
2. **Derived episodes:** source-linked, temporally bounded, uncertainty-labelled and supersedable.
3. **Hierarchical summaries:** digest-keyed, versioned, resumable and linked to child nodes.
4. **Whole-person model:** provisional, versioned, source-validated and never equivalent to diagnosis or risk.
5. **Task context:** budgeted read-only compilation for a specific authorised agent/task; retrieved text is untrusted evidence, not instructions.

## Publication and consistency
A build has a correlation ID, source watermark, prompt/schema versions, digest, status and error category. The last good active model remains available until the candidate is fully validated and persisted. Partial processing must be visible and must not be reported as fresh success. Late-arriving or corrected sources invalidate relevant derived digests and trigger a bounded rebuild without rewriting source rows.

## API and UI contract
Expose version ID, generated-at time, source watermark, status, limitations, provenance and whether the version is stale. Distinguish `ready`, `processing`, `partial`, `failed`, `consent_required`, `consent_revoked`, `no_source_evidence`, `research_only`, `shadow` and `insufficient_data`. The therapist view must verify assignment-level authorisation on every read and must not leak data to unassigned professionals or administrative roles. Do not label a behavior-change deviation as a clinical crisis.

## Care operations and scarcity-aware resource allocation
Queue prioritisation may use approved, validated signals, time-sensitivity, clinical protocol and time since last human review. Allocation must constrain by staff competency/credential, assigned relationship, availability, caseload, continuity, SLA and patient preference. Human professionals approve assignments/actions. The system must not deny/reduce access because of missing observations or a low model score. Audit assignment proposals, override/rejection, reason, task completion and outcome. Deterministic crisis protocols remain independent of workload optimizers.

## Data and interoperability
Do not rename or replace existing tables for the remodel. Define a versioned adapter with canonical event time vs ingestion/recorded time, units, original value/code, normalised code and version, provenance, consent purpose/scope, source row ID and missingness. FHIR R4 mappings may be implemented at an integration boundary (Observation, Condition, MedicationRequest/Statement, Encounter, QuestionnaireResponse, Provenance, Consent, Task), preserving original values and schema. Any schema change is additive and requires reviewed migration, RLS checks, backup and parity validation.

## Infrastructure
- **Now:** Supabase/PostgreSQL remains the data source of truth; Render remains web/API/initial orchestration. Fix measured bottlenecks before vendor migration.
- **Modal later:** isolated, replaceable ML compute only, if benchmarks justify it. Review region for all ingress/routing/execution, DPA, sub-processors, transfer mechanisms, logs, volumes/snapshots, retention/deletion, audit and cost. Send only minimum necessary payload after consent/auth check. It does not replace PostgreSQL, auth, RLS or audit.
- Current provider deployments do not prove clinical/regulatory suitability; product owner/DPO/clinical lead must explicitly approve intended purpose and data path.

## Deployment
Use a review branch and CI first. Production remains attached to the existing database and service URLs during the branding/research phase. No production replay or deploy occurs as a side effect of a documentation or code change.


## Additive integration with the existing four LLM agents
The four-agent LLM orchestration is a preserved product capability, not a migration target. Do not remove, merge, replace, rename or silently reroute any existing agent/provider, memory/context path, tool permission or workflow as part of predictive-model work. New predictive capabilities are separate services behind typed contracts. Existing agents may call a prediction/read API only when authorized and consent permits, and must show the model status, horizon, evidence and uncertainty verbatim. They cannot fabricate scores, promote models, access training data by default, or convert research/shadow predictions into clinical recommendations. The deterministic safety plane and current four-agent workflows continue to function if the ML service is unavailable.

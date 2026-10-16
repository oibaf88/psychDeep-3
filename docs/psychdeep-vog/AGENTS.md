# psychDeep-vOG — agent contract

## Mission
Build a longitudinal psychiatric-care and clinical collaboration platform with three linked outcomes:
1. Predict prespecified outpatient deterioration outcomes from longitudinal clinical data, but only after rigorous validation.
2. Detect meaningful, consented behavioural/digital changes relative to a person's own baseline without treating proxies as diagnoses.
3. Support patient accompaniment and make limited therapist/clinical-team capacity more effective through transparent, human-controlled task coordination.

The app is not primarily a chatbot. Memory, summaries and LLM agents support the mission; they do not constitute the product outcome. Current implementation status must be described honestly: target architecture and plans do not prove a deployed model or validated clinical prediction exists.

## Start here
1. Root `AGENTS.md` and the current product specification.
2. `CORE_PRODUCT_FUNCTIONALITIES.md`, `ARCHITECTURE.md`, `PREDICTIVE_MODEL_PLAN.md`, `FEATURE_DATA_CONTRACT.md`, `CARE_COORDINATION.md`, `DATA_PRESERVATION.md`, `IMPLEMENTATION_PLAN.md`, `CLINICAL_VALIDATION.md` and `OPERATIONS_RUNBOOK.md`.
3. The relevant ADRs, API schemas, database migrations and tests.

## Hard constraints
- Preserve every existing clinical source row, stable identifier, timestamp, consent, audit trail, provenance link and historical version.
- Do not drop/recreate tables, truncate tables, reset production, or replace source records with generated summaries.
- Keep current Supabase production project/schema as the source of truth until a separately approved migration passes parity and rollback gates.
- Derived models are versioned projections. Publish a new active version only after complete validation and persistence; retain the last good version on failure.
- Enforce purpose-specific consent before and after external model calls. Do not log clinical text, prompts, outputs, credentials or exception messages.
- Keep crisis/safety decisions deterministic and independent from LLM and research-model outputs.
- Never interpret prescribed medication as proof of adherence; do not infer symptoms from one linguistic or interaction feature.
- Missing, unavailable, late or not-consented data are not normal values and not reassurance.
- Do not deploy an unvalidated predictive model or show fabricated probabilities. Label research-only outputs explicitly.
- Care-task prioritisation must distinguish clinical urgency from operational workload; no automatic denial of care or punitive staff decisions based solely on model outputs.
- Never replay dead-letter jobs, deploy or merge production changes automatically.

## Implementation standard
- Define/version every external and internal contract.
- Make jobs idempotent under duplicate delivery and safe after process restart.
- Validate exact source coverage and reject unknown references.
- Use bounded retries, explicit dead-letter states, correlation IDs and safe frame-only exception telemetry.
- Include backend and frontend regression tests, negative authorization tests and a data-preservation test plan.
- Represent loading, stale, partial, failed, consent-required, no-evidence and research-only states distinctly.
- Every inferred statement must expose perspective, uncertainty, provenance and source references.
- Establish target, index time, outcome label, horizon and evaluation split before training.
- Require temporal validation, calibration, subgroup assessment, clinical utility and workload-impact assessment before clinical release.

## Daily agents/bots
Daily agents may produce a non-PHI operational report from aggregate telemetry and CI: error categories, code locations, retry/dead-letter counts, oldest pending job, freshness of last successful model, API/UI contract status, test status, feature/data quality coverage and open work. They may propose tickets/patches. They must not inspect patient text, change consent, replay jobs, alter production data, change environment secrets or deploy without a human-approved runbook.

## Definition of done
- Tests and checks are named with results; unknown/unrun checks are stated as such.
- Source rows and historical versions remain unchanged.
- A failed rebuild cannot replace the last good model.
- Memory is visible only to the patient or an assigned authorised professional.
- Predictive outputs are absent or explicitly research-only until validation gates pass.
- A care task has an owner, due window, priority rationale, audit history and outcome.
- Rollback and recovery instructions exist.
- A human reviewer approves clinical interpretation changes and production rollout.

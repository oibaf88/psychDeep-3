# psychDeep-vOG predictive model research — implementation brief

The full literature review and target architecture live in `docs/psychdeep-vog/PREDICTIVE_MODEL_RESEARCH_AND_TARGET_ARCHITECTURE.md`. This brief translates it into next implementation work.

## Product pillars
- Outpatient deterioration prediction using longitudinal temporal deep-learning, only after an observable target is defined and data adequacy established.
- Individualized longitudinal behavioral/digital-change prediction using consented EMA/check-ins/diary first. Passive sensing is out-of-scope for the first research release.
- Human-reviewed care coordination and resource allocation using documented evidence, permissions, staff skills/capacity, and audited workflows.

## Non-negotiables
- Existing `psychdeep_v12` remains the production source of truth. Additive, backward-compatible changes only after review.
- Existing check-in/diary/observation ingestion continues; no table rename/drop, reset, migration execution, or source data rewrite in this effort.
- Existing deterministic crisis/risk engine stays independent from LLM and predictive-model outputs.
- Do not show unvalidated scores in patient/professional workflows. Research -> silent retrospective -> shadow prospective -> clinically reviewed assisted use.
- Consent is modality- and purpose-specific; check it at collection, feature extraction, model call, prediction publication and withdrawal handling.
- No clinical content in routine telemetry or CI artifacts.

## Model research
- EHR: benchmark simple calibrated baseline vs RETAIN/GRU-D and compact time-aware Transformer. Evaluate BEHRT/Hi-BEHRT only if data scale, terminology, licence and transferability justify it; no training a large transformer from scratch on a small pilot.
- Digital/EMA: structured EMA-only and text-only first; then late fusion. Compare simple temporal models and embeddings before fine-tuning an encoder. Person-specific baseline, irregular-time embeddings and explicit missingness.
- Labels: require clinician-approved target, event date, index time, censoring and horizon. 14–28 day and 48–72 hour alert horizons are research hypotheses, not promises.
- Evaluation: patient/time-separated splits, rolling-origin, locked temporal test; AUPRC, AUROC, Brier, calibration slope/intercept, sensitivity/PPV at predeclared thresholds, false alerts per person-month, lead time, decision utility, subgroup evaluation and confidence intervals.
- No medication-adherence inference without valid dispensing/exposure data. No passive GPS, keyboard, contacts or third-party messages by default.

## Acceptance criteria for first engineering PRs
1. Read-only dataset/feature contract maps existing source table/columns, event vs recording time, unit, provenance, consent scope, source ref, missingness and normalisation version.
2. Aggregate data audit (no row-level patient data in logs/PR) reports patients, event coverage/frequency, follow-up and target event counts.
3. Label specification and split manifest are versioned and reproducible. No post-index records can leak into features.
4. Offline benchmark reports every model and baseline against the same locked test split; abstains for insufficient data.
5. Shadow model produces versioned artifacts only; no existing risk/alert field is overwritten; prior active model remains available.
6. Care operations start as human-owned task queue with staff competence/capacity, patient assignment, due date/SLA, feedback and audit; prediction never auto-contacts or denies care.
7. Privacy/legal gate covers GDPR special-category basis, DPIA, MDR Rule 11, AI Act intersection, FHIR mappings, subprocessors, EU data locality and transfer conditions.
8. Supabase/Render stay in place while stable source data is valuable. Modal is evaluated as isolated compute only after regional routing, DPA/contract, logging, storage/snapshot and retention are verified.

## Infrastructure verdict
Supabase PostgreSQL is the best current option for continuity, existing data, auth/RLS, provenance and vectors. Current DB advisories merit controlled remediation but do not justify migration alone. Render is acceptable for the current API/web footprint; verify plan/backups/observability before clinical operationalisation. Modal could serve bursty training/inference but is not a replacement database and must not receive real clinical payloads before formal privacy and contract review.

## Current implementation status — must remain explicit
Existing product supports check-ins/EMA-like observations, baselines/change signals, consent, assignments, patient longitudinal memory and a deterministic risk engine. Memory synthesis is LLM-driven and is not a validated deterioration predictor. The predictive deep-learning models, validated outcome labels, clinical benchmarking and validated staff allocation logic do not yet exist as production capabilities.

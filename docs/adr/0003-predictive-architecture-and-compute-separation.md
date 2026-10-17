# ADR-0003: Predictive architecture and separation of compute from clinical source of truth

- **Status:** Proposed for review
- **Date:** 2026-10-16
- **Decision owners:** Product owner, clinical lead, data protection officer, engineering lead
- **Depends on:** MDR/AI Act intended-purpose assessment, data/outcome audit, clinical validation protocol

## Context

psychDeep has a live longitudinal pilot in Supabase PostgreSQL schema `psychdeep_v12`, a Render-hosted FastAPI API and static frontend, consent/assignment controls, an existing deterministic risk engine, canonical observations/baselines/change signals and a separately generated LLM memory. The application lacks evidence that it currently runs clinically validated deep-learning predictors of deterioration or digital behavioral change.

The pilot's records and ongoing submissions must remain available. There is no demonstrated performance need that justifies a database migration now. Predictive ML needs a separate experimental and release lifecycle from the LLM memory and deterministic safety path.

## Proposed decision

1. Preserve Supabase as the only clinical transactional system of record.
2. Retain Render for API/frontend and initially for lightweight orchestration/workers.
3. Build a read-only feature/data adapter over current tables. Do not use inferred summaries as substitutes for source features. Do not write raw export rows back to the source schema.
4. Evaluate in this order:
   - patient/time-split baselines (calibrated logistic/survival and current clinical process);
   - temporal interpretable/deep baseline (RETAIN, GRU-D/GRU with delta-time and missingness);
   - compact time-aware Transformer;
   - BEHRT/Hi-BEHRT-type transfer only if pretraining scale, Spanish/local coding, licensing and data adequacy are defensible;
   - separate structured EMA and language temporal encoders, then calibrated late fusion.
5. Keep separate contracts for:
   - deterministic crisis and safety;
   - LLM-based longitudinal memory;
   - unvalidated research predictors;
   - clinically approved predictor output;
   - human-owned care tasks.
6. Use Modal only as optional isolated compute in a later phase if bursty training/inference merits it. Modal cannot become a second clinical database or bypass authorization/consent. Only pseudonymized/minimized data or de-identified development data may be sent until region, ingress/routing, logs, volumes/snapshots, contracts, processors/transfers and DPIA gates are formally met.
7. Any clinically interpretable output remains disabled for care decisions until outcome labels, target, calibration, external/temporal validation, clinical utility, fairness, regulation and human workflow gates are reviewed and approved.

## Consequences

- Minimal risk to the ongoing pilot and compatibility of current collection.
- More explicit model registry, target/feature contracts, provenance, audit, and release lifecycle.
- Short-term cost of running paired baselines and data-quality audits before choosing a neural architecture.
- May require a separately governed dataset/experiment store and model-artifact registry; neither should hold the authoritative patient history.
- Model performance cannot be claimed based on published AUC from unrelated outcomes/populations.
- Product UI should call outputs "research / shadow" until release gate passed and should expose missingness, evidence, horizon and uncertainty.

## Rejected alternatives

- **Migrate production DB to Render now:** unnecessary disruption to a live pilot; no current performance evidence justifying it.
- **Move all systems to Modal:** it is compute-oriented and does not replace the requirements met by the transactional store, authorization and audit system; it increases data movement and vendor/legal review burden.
- **Make an LLM prompt act as a risk predictor:** lacks target-specific validation/calibration and creates unsafe conflation of narrative interpretation with clinical risk.
- **Choose BEHRT/Hi-BEHRT as final model now:** paper results on broad EHR prediction do not establish transferability to this psychiatric pilot or its targets.
- **Begin passive smartphone surveillance by default:** disproportionate and not necessary to establish value from already collected EMA/check-ins/diary.

## Gates before implementation or release

- [ ] Data audit and feature availability matrix completed with aggregate metrics only.
- [ ] Clinical target, index time, prediction horizon and action pathways signed off.
- [ ] GDPR purpose/basis, DPIA, consent scopes and withdrawal semantics reviewed.
- [ ] MDR/AI Act intended-purpose assessment completed.
- [ ] Read-only feature builder tested for temporal leakage, duplicates, missingness and determinism.
- [ ] Benchmarks report locked-test discrimination, calibration, clinical utility, uncertainty and alert burden.
- [ ] Prospective shadow mode and clinical review completed.
- [ ] Infrastructure/vendor and Modal data-path review completed if used.

# psychDeep-vOG architecture

## Product mission
psychDeep-vOG combines three core capabilities: (1) longitudinal outpatient deterioration modelling, (2) consented detection of behavioural/digital changes against a person's own baseline, and (3) accompaniment plus human-care coordination under limited clinical capacity. It is not primarily a chatbot. See `CORE_PRODUCT_FUNCTIONALITIES.md`, `PREDICTIVE_MODEL_PLAN.md`, `FEATURE_DATA_CONTRACT.md` and `CARE_COORDINATION.md`.

These are target capabilities, not a claim that validated prediction models or automated workforce allocation currently exist. Until validation gates pass, the app must not show fabricated probabilities or present research outputs as clinical decisions.

## System of record
The existing Supabase PostgreSQL project and `psychdeep_v12` schema remain the sole production clinical source of truth. Render hosts the web frontend and API/worker. Model providers sit behind the existing provider-neutral Model Gateway. A provider outage must not disable source storage, deterministic safety processing or access to the last successful memory version.

## Logical flow
```text
Existing clinical sources + patient-reported/consented observations
             |
             v
Purpose-specific consent + identity/role/assignment authorisation
             |
             v
Immutable source history / event-time normalisation / quality checks
             |
             +-----------------------------+
             |                             |
             v                             v
Clinical timeline & memory         Consented digital/EMA feature pipeline
             |                             |
             v                             v
Outpatient cohort/feature pipeline   Person-specific baseline & change signals
             |                             |
             v                             v
Validated outcome model              Temporal behavioural-change model
             |                             |
             +--------------+--------------+
                            v
          Evidence/provenance + uncertainty + freshness
                            |
                            v
           Distinguish change signal from predicted risk
                            |
                            v
      Existing deterministic safety pathways + human review
                            |
                            v
     Care task queue -> eligibility/capacity matching -> human assignment
                            |
                            v
            Accompaniment -> action/outcome feedback -> evaluation
```

The diagram describes a target architecture. Model outputs may feed operational queues only after the relevant validation and governance gate has passed.

## Memory layers
1. **Source records:** immutable from the memory pipeline's perspective; normal user/clinician correction flows retain their own audit history.
2. **Derived episodes:** source-linked, temporally bounded, uncertainty-labelled and supersedable.
3. **Hierarchical summaries:** digest-keyed, versioned, resumable and linked to child nodes.
4. **Whole-person model:** provisional, versioned, source-validated and never equivalent to diagnosis or risk.
5. **Feature/change layer:** versioned feature definitions and baseline comparisons with explicit missingness; do not conflate with clinical risk.
6. **Prediction layer:** only approved model versions with target, horizon, calibration, intended use, training/evaluation lineage and status.
7. **Care-task layer:** source/evidence-linked tasks, priority rationale, owner, due window, assignment history and outcome.
8. **Task context:** budgeted read-only compilation for a specific authorised agent/task; retrieved text is untrusted evidence, not instructions.

## Publication and consistency
A build has a correlation ID, source watermark, prompt/schema/feature/model versions, digest, status and error category. The last good active model remains available until the candidate is fully validated and persisted. Partial processing must be visible and must not be reported as fresh success. Late-arriving or corrected sources invalidate relevant derived digests and trigger a bounded rebuild without rewriting source rows.

## Temporal and multimodal contract
Every event keeps event time distinct from recorded/ingested time, with timezone/precision, source/modality, quality, missingness and consent context. Feature windows are anchored to an explicit prediction cutoff. Never use post-outcome data. Missing data are not zero or reassurance. Medication prescribed, dispensed, reported and confirmed taken are distinct states. A text style feature, message latency or usage gap is not a clinical fact by itself.

## Alert and workflow semantics
Separate observed facts, baseline-relative change signals, predicted outcomes, clinical urgency and operational task priority. The existing approved deterministic safety path remains independent of LLMs and predictive-model availability. A research-only or unvalidated model must not determine clinical urgency or enter a production alert queue.

## API and UI contract
Expose version ID, generated-at time, source watermark, status, limitations, provenance, consent state, missingness and whether the version is stale. Distinguish `ready`, `processing`, `partial`, `failed`, `consent_required`, `consent_revoked`, `no_source_evidence` and `research_only`. The therapist view must verify assignment-level authorisation on every read and must not leak data to unassigned professionals or administrative roles.

## Deployment
Use a review branch and CI first. Production remains attached to the existing database and service URLs during the branding/repair phase. No production replay or deploy occurs as a side effect of a documentation or code change. Any future schema extension must be additive, reviewed and tested against preserved data.

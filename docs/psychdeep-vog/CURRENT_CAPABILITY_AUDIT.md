# psychDeep-vOG current capability audit

**Evidence basis:** read-only inspection of current `master` source files and a metadata-only table inventory. This is a code/schema capability assessment, not an end-to-end runtime certification. No patient rows were queried and no production data was changed.

## Capability matrix

| Core capability | Evidence in current code/schema | Status | Critical gap before claiming product-ready |
|---|---|---|---|
| Canonical longitudinal observations | `backend/app/models_vnext.py`: `Observation`, event/received timestamps, quality and consent reference; `observations` table exists | Foundation present | Audit all source mappings, consent semantics, late arrivals and source coverage |
| Personal baseline and change detection | `canonical_analytics.py`, `longitudinal_read.py`; check-ins dual-write mood, craving, sleep hours and self-efficacy; recent/reference windows are versioned | Partial foundation present | Validate feature coverage, baseline eligibility, clinical thresholds and alert burden; population-derived bands remain provisional |
| Existing deterministic safety/risk workflow | `risk_engine.py`; explicitly deterministic and separate from LLM; code labels its operational rules as not a validated scale | Operational rules present; not a validated predictive model | Clinical review, workflow evaluation and safety validation; never describe current score as a calibrated probability of future deterioration |
| Longitudinal memory and summaries | Memory tables/services, source references, model versions, job history and failure telemetry exist | Partial; runtime generation reliability remains unresolved | Resolve the outstanding episode-pipeline TypeError using synthetic reproduction; verify atomic publish and last-good retention; prove end-to-end therapist integration |
| Consented digital/language change | `profile.py` maintains a linguistic baseline from stored signals; purpose-specific consent APIs exist | Partial / narrow | Audit exactly which sources are processed and consent-enforced; add temporal reference evaluation; no passive footprint or sequence-model capability is assumed |
| EMA / patient-reported outcomes | Check-in schema currently includes mood, craving, sleep hours, self-efficacy and optional notes | Partial | Clinically review instrument definitions, versioning, frequency, burden and missingness; these fields are not automatically equivalent to a validated EMA battery |
| EHR / prescription / pharmacy integration | No source-backed EHR/pharmacy connector was established by this inspection | Not demonstrated | Define interfaces, provenance, coverage and data-sharing authority before building adherence features |
| Trained deterioration prediction | Canonical features, inferences and model-run metadata exist, but the inspected risk engine is deterministic rule logic and no validated target/horizon/model evidence was found | Not demonstrated as a validated model | Specify outcomes and cohort, build simple baselines, temporal/external validation, calibration and prospective silent mode |
| Human assignment and consent | Assignment lifecycle, professional roles, consent history, audit and role-scoped professional APIs exist | Foundation present | Verify assignment restrictions and consent propagation; team/supervisor scoping needs review |
| Care task queue / capacity matching | Professional alerts, notifications and assignments exist; no dedicated task lifecycle with due time, estimated duration, competency matching, availability/capacity and outcome was established | Not demonstrated | Map service workflows; design and test task model and allocation UI on synthetic data; require human assignment |
| Operational monitoring | Audit log, risk assessment traces, model-run and memory-job tables exist | Partial | Aggregate, privacy-safe metrics for stale data, model freshness, alert burden, task SLAs and capacity are not yet proven end-to-end |

## Key implementation conclusions

1. **The current strongest foundation is deterministic, within-person change detection from check-ins**, not a validated future-risk prediction model.
2. The existing risk engine is a separate deterministic safety/operational-rules pathway. Its outputs must not be renamed as ML predictions or calibrated probabilities.
3. The app does not yet demonstrate the outpatient EHR/medication data pipeline described in the product target.
4. Existing consent and patient-professional assignment concepts should be reused; do not create parallel identity or consent systems.
5. Existing alerts and notifications are not a substitute for a care-task lifecycle or resource-capacity model.
6. Memory generation reliability is a blocker for treating longitudinal memory as a dependable shared service. Resolve it independently and keep the last good version available.
7. Do not start with BEHRT/Transformer or multimodal deep learning. First build a validated outcome definition, data-quality map, leakage-safe cohort and simple baseline.

## Recommended implementation order

1. **Reliability gate:** reproduce and fix memory-pipeline failure with synthetic fixtures; verify last-good model behaviour and current therapist-memory UI.
2. **Data/source mapping:** create a feature/source inventory for check-ins, diary, chat, clinical documents, signals, diagnoses, medication and service use; explicitly mark unavailable sources.
3. **Clinical endpoint protocol:** agree primary outcome, index time, exclusions, adjudication and prediction horizons.
4. **Research pipeline:** produce a de-identified/synthetic cohort, data-quality report and simple baseline; no production score.
5. **Behavioural-change validation:** define personal-baseline eligibility, confounders and prospective reference collection for consented text/EMA features.
6. **Care operations:** inventory existing alert and assignment workflow; prototype task queue/capacity matching using synthetic records before schema changes.
7. **Prospective silent mode:** measure calibration, false alerts, lead time, workload and equity before enabling any predictive output in clinical care.

## Validation boundary
The audit does not certify the deployed app in a browser, prove that every permission check is correct, or establish clinical performance. Those require explicit automated tests, end-to-end testing and clinical validation.

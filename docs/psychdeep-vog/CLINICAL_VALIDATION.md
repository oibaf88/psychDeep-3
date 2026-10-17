# Clinical validation plan

## Intended use and boundaries

### Longitudinal memory
Memory is a provisional, source-linked aid to longitudinal review and session preparation. It is not a diagnosis, risk score, treatment recommendation or autonomous clinical decision. Deterministic safety/risk systems remain independent.

### Predictive model A — outpatient deterioration
Target-specific prediction of a pre-defined clinical event/change over a declared future horizon, from verified longitudinal structured/semi-structured sources. Do not call a model clinically predictive unless that target, time-origin, censoring and horizon are explicit, temporally validated and reviewed for intended use.

### Predictive model B — individual digital/behavioral change
Prediction of deviations from a person's baseline using consented EMA/check-ins/diary and other specifically authorised modalities. A deviation is not synonymous with relapse, diagnosis, crisis or need for intervention. Passive sensing is out of scope unless separately approved.

### Human care coordination
Predicted signals can support a human review queue only after an approved release. They cannot independently diagnose, prescribe, contact third parties, initiate coercive actions, or reduce access to care. A deterministic safety protocol remains independent of any learned predictor.

## Validation dimensions — shared foundation
1. **Source fidelity:** every claim links to valid source IDs; no invented references; quotations remain distinct from interpretations.
2. **Temporal fidelity:** event time and record/ingestion time remain distinct; order, duration, time zones, late-arriving records and context changes are handled correctly.
3. **Epistemic separation:** patient report, professional report, third-party report, system observation, derived feature and model hypothesis remain distinct.
4. **Contradictions and corrections:** conflicts are preserved with uncertainty; corrections supersede only the appropriate derived interpretation, never erase source history.
5. **Coverage and omissions:** batches/features account for included/excluded sources; missing data does not silently become a zero, normality or low risk.
6. **Stability:** identical source snapshot + code/model/feature-contract version yields reproducible dataset manifest and version metadata; writes are idempotent.
7. **Safety and consent:** consent is checked at collection, feature building, inference and publication; revocation blocks future processing and is handled according to approved retention/deletion requirements; authorization follows assignment/role.
8. **Human usability:** patients/professionals can inspect sources and limitations, add context/corrections, and distinguish stale, partial, failed and current results.
9. **Privacy:** use synthetic or appropriately de-identified fixtures for CI; do not copy patient text, prompts, predictions linked to identity or secrets into routine logs/artifacts.
10. **Equity and non-coercion:** measure subgroup performance and burden where lawful and sufficiently supported; missing engagement or low data volume may not be used to penalise or deprioritise a patient.

## Predictive model evaluation protocol

### A. Target and cohort preregistration
- State the intended population, eligibility, outcome definition, data sources, prediction index time, lookback window, target horizon, competing events/censoring and permitted clinical response before model training.
- Define the label through a clinician-approved data source or adjudication process. Do not treat medication change, cancelled appointment, absence of a check-in, language style or an LLM hypothesis as relapse ground truth.
- State how many independent patients, positive events, follow-up periods and usable event sequences exist. If insufficient for the intended design, report infeasibility rather than fitting a complex model.
- Pre-specify the operational cost of false negatives, false positives, over-alerting, delayed alerts and unnecessary patient contact.

### B. Dataset splits and leakage control
- Split by person and time; all records/windows from the same patient remain within one split unless a formally justified alternative answers a distinct use question.
- Use rolling-origin temporal validation and a locked temporal test set. Use external validation where a suitably comparable independent cohort exists.
- Features must be available at or before the prediction index. Never use future notes, post-outcome diagnoses, treatment changes triggered by the outcome, or summaries that incorporate future information.
- Fit imputation, scaling, feature selection, vocabulary adaptation, model tuning and calibration only on allowed training/validation folds.
- Test delayed records, timezone boundaries, repeated/duplicate entries, changing scales and irregular sampling.
- Keep missingness explicit; compare missingness-aware methods and sensitivity analyses rather than imputing “normal”.

### C. Benchmark ladder
Compare identical cohort, outcome, horizon, split and decision protocol:
1. Existing clinical/current-practice comparator where defensible.
2. Calibrated logistic/elastic-net or survival baseline.
3. Temporal interpretable baseline (e.g. RETAIN) and/or GRU-D/GRU with explicit time deltas and masks.
4. Compact time-aware Transformer with irregular-time encoding.
5. BEHRT/Hi-BEHRT-style transfer only if model license, vocabulary, language, event volume and target transfer are suitable.
6. For digital/behavioral change: structured EMA only, consented text only, then late fusion. Assess per-modality contributions and data availability before choosing a fusion model.

The highest AUROC alone does not establish best clinical model. Prefer the simplest model that meets pre-specified clinical utility, calibration, equity and operations requirements.

### D. Metrics to pre-specify
- **Discrimination:** AUPRC (important for rare outcomes), AUROC as secondary.
- **Calibration:** Brier score, calibration-in-the-large, slope, reliability curve; report uncertainty.
- **Decision performance:** sensitivity, PPV, specificity and NPV at thresholds chosen with clinicians before final test analysis.
- **Operations:** false alerts per patient-month, true actionable alerts, time-to-review, useful lead time, missed events, abstention/insufficient-data rate, repeated-alert burden and workload created.
- **Clinical utility:** decision-curve/net benefit when assumptions fit; impact on relevant workflow outcomes and patient/clinician acceptability.
- **Robustness and fairness:** performance/calibration by clinically meaningful and lawfully available groups, confidence intervals clustered by patient, missingness/coverage subgroups, temporal drift and external generalisation.
- **Comparator and uncertainty:** incremental benefit over baseline and confidence intervals; no performance statement without split and cohort context.

Clinicians and product/data-protection leads must approve the thresholds before reviewing the final locked test results. Do not tune thresholds against the final test set.

### E. Release stages
1. **Offline retrospective research:** immutable dataset manifest; results not shown to care teams/patients.
2. **Prospective shadow:** run without affecting treatment or task allocation; adjudicate false positives, misses, burden and meaningful lead time.
3. **Supervised assisted use:** only after clinical safety, privacy/legal, calibration, utility, usability and workflow gates pass; every signal has human review and override.
4. **Ongoing monitoring:** drift, calibration decay, source shifts, subgroup differences, abstention, alerts per patient and outcomes. Any retraining, model promotion or threshold change is versioned, audited and reviewed.

## Memory model evaluation
- Use a clinician-reviewed gold set with source references and explicit uncertainty labels.
- Double-review a sample; record agreement and adjudication for factuality, temporal ordering, unsupported inference, contradiction handling and clinical usefulness.
- Track per-version prompt/schema/model provenance, test-set version, evaluation date and reviewer role.

## Legal, privacy and intended-purpose gate
Before any individual prediction is exposed for care: assess GDPR Articles 6/9 basis, transparency and data subject rights, necessity of a DPIA, modality-specific consent where relied upon, processor/subprocessor contracts and data flows, and access/retention controls. Obtain qualified assessment of intended purpose and potential medical-device status under MDR/Rule 11 plus applicable AI Act obligations. A label such as “research”, “support” or “wellbeing” does not by itself determine regulatory status.

## Release gates
No claim of clinical validation until a reviewed protocol, adequate representative dataset, pre-specified metrics, temporal/external validation appropriate to the claim, calibration, clinical utility evaluation, independent review and documented results exist. Technical correctness, predictive performance, clinical usefulness, legal suitability and service availability are distinct criteria. Any model/feature/threshold change affecting clinical interpretation requires regression evaluation and review.

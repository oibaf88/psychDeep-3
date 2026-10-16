# Predictive model development and validation plan

## Scope and status

This is a research and engineering plan, not a claim that predictive models are currently trained, validated or in clinical use. Initial work must establish outcome labels, data quality, temporal cohorts and simple baselines before using Transformers or multimodal fusion.

Two related but separate modelling tasks are proposed.

## A. Outpatient deterioration prediction

### Target definition first
Before feature development, the clinical team must define a primary outcome that is reproducible in retrospective data (for example, a prespecified acute-care contact or adjudicated deterioration event), inclusion/exclusion criteria, index time, competing events and label adjudication. Do not treat a diagnosis-code change, missed appointment, prescription change or emergency attendance as interchangeable proxies for deterioration.

Candidate horizons to evaluate include 14 and 28 days. These are hypotheses for study design, not a promised warning window or guaranteed lead time.

### Candidate inputs
- Diagnoses and clinical events with coded value, source, event time and recorded time.
- Prescriptions and medication changes, explicitly distinguishing prescribed, dispensed, reported and confirmed taken.
- Adherence metrics such as PDC/MPR only when pharmacy coverage and days-supply data support valid calculation; encode unknown as unknown.
- Service-use signals: appointment attendance/cancellation, unscheduled contact and urgent-care events, with source coverage and service-specific ascertainment.
- Standardised EMA and clinical scales, with instrument/version, completion time and missingness.
- Relevant context and protective factors where lawful, consented, clinically reviewed and consistently encoded.

### Modelling sequence
1. Data audit and label protocol; leakage assessment and cohort flow.
2. Transparent baselines: prevalence, regularised logistic regression and/or gradient-boosted trees.
3. Temporal baseline: discrete-time survival or other time-aware model, selected according to event and censoring structure.
4. Compare GRU/LSTM and time-aware Transformer (e.g. BEHRT-like temporal embeddings) only if sample size and event density justify the added complexity.
5. Add multimodal fusion only after each modality has standalone validity and data coverage is characterised.
6. Evaluate incremental value against baseline and current clinical workflow; complexity must earn its place.

Irregular event timing should be represented explicitly (time since prior event, time since medication change, age/time features as appropriate). The model must account for informative observation: people with more clinical contacts may appear to have more events simply because they are observed more often.

## B. Consented digital/behavioural change detection

### Inputs and consent
Potential inputs include patient-entered diary text, explicitly shared conversation excerpts, EMA responses, and sleep/activity data from an explicitly connected source. Use only data the person has been informed about and consented to for this purpose. Passive surveillance is not a default assumption.

Potential language features include validated semantic/emotion representations and longitudinal style measures. First-person pronouns, absolutist words, message length, response latency and nighttime activity are context-sensitive correlates, not diagnostic facts. They must never trigger clinical escalation on their own.

### Modelling sequence
1. Establish a per-person baseline only after a prespecified minimum number and spread of observations; document baseline eligibility and stability.
2. Start with interpretable, robust change statistics and quality flags.
3. Evaluate text embeddings/classifiers and sequence models (e.g. hierarchical GRU/LSTM) only against a reviewed reference standard.
4. Test confounding by language, culture, disability, device access, work schedule, social context, medication effects and changes in app usage.
5. Compare multimodal fusion to single-modality models and an abstention/no-prediction policy.
6. Make consent revocation, data deletion/retention policy and model-input exclusion behaviour testable.

A 48–72-hour alert window is a hypothesis to evaluate, not a performance promise.

## Fusion and time handling
Represent each event with at least:
- event time and ingestion/recorded time, with timezone;
- source/modality and provenance;
- value/unit or content-derived feature version;
- missingness/quality and measurement method;
- consent and access context;
- feature definition version and transformation version.

Use an explicit cutoff at prediction time. No future data, post-outcome notes, labels derived after the index point, or future prescription status may enter features. Preserve irregular intervals rather than padding them into apparently regular observations without masks/time deltas.

## Evaluation protocol
- Split by patient and time; all observations for a patient must not leak across train/test partitions where that would inflate performance.
- Use temporal holdout first, then external-site/period validation where feasible.
- Report discrimination (AUROC and AUPRC), calibration (calibration plot/slope/intercept and Brier score), sensitivity, specificity, PPV/NPV at operational thresholds, lead time, alert burden per patient-time, missingness and abstention rates.
- Report subgroup performance and calibration for clinically and socially relevant groups where lawful and sufficiently powered; investigate unequal false positives, false negatives and access-related missingness.
- Compare against prevalence, simple baselines and current care processes.
- Perform decision-curve / net-benefit analysis and prospective silent-mode evaluation before clinical use.
- Evaluate whether alerts improve actionable detection and outcomes, not merely model metrics.
- Predefine threshold, intended user, response SLA, escalation pathway and harms of false reassurance/over-alerting.

No universal performance threshold should be selected after seeing the test results. Thresholds require clinical and operational governance.

## Clinical and operational release gates
1. Data validity and outcome adjudication accepted by clinical reviewers.
2. Reproducible temporal evaluation and leakage audit.
3. Calibration and subgroup analysis acceptable for intended use.
4. Prospective silent-mode validation with alert volume and workload impact.
5. Human-factors testing of explanations and workflow.
6. Prospective evaluation of clinical utility and resource effects.
7. Formal approval, model card, monitoring, rollback and incident plan.

Until these gates pass, models are research-only. The production UI must distinguish research output from validated clinical functionality.

## Monitoring and rollback
Monitor drift, calibration, missingness, data-source availability, alert rate, clinician overrides, response times and downstream outcomes. If performance or data quality degrades, disable the model output while preserving source data, audit history and the last approved version. LLMs may explain source-linked evidence in bounded language but must not manufacture numeric risk scores.

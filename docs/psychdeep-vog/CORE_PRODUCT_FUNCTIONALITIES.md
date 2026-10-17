# psychDeep-vOG — core product functionalities

## Product purpose

psychDeep-vOG is a longitudinal psychiatric-care and clinical collaboration platform designed to (1) identify meaningful within-person changes that may precede deterioration, (2) support early, proportionate accompaniment, and (3) help scarce human clinical resources reach the people and tasks that most need them. It is not primarily a chatbot and must not present an unvalidated model as a clinical predictor.

The product combines three linked capabilities:

1. **Outpatient deterioration modelling:** integrate longitudinal structured and semi-structured clinical data to estimate a clearly defined future outcome over a specified horizon.
2. **Consented behavioural/digital change detection:** identify deviations from the person's own baseline in consented check-ins, diaries, language and other legitimately collected signals.
3. **Care coordination and workforce support:** convert reviewed signals into follow-up tasks, session preparation, caseload visibility and accountable allocation of human attention.

Memory, summaries, LLM agents and conversational accompaniment are supporting infrastructure and interfaces—not substitutes for these three outcomes.

## Core user journeys

### Patient
- Understand their own trajectory and what evidence supports a detected change.
- Complete voluntary, low-burden EMA/check-ins and review what data are collected.
- Add context, correct a factual error, disagree with an interpretation, pause sharing, or withdraw optional data-processing consent without silently erasing clinical history that must be retained under applicable rules.
- Receive proportionate self-regulation and follow-up options, with clear access to human help.
- See when an observation is uncertain or unavailable; missing data must never be presented as reassurance.

### Therapist / care team
- See an assigned caseload, current follow-up obligations and transparent reasons for prioritisation.
- Review longitudinal clinical and patient-reported evidence, change from personal baseline, uncertainty, missingness, protective factors and contradictory information.
- Prepare sessions using source-linked summaries and prior agreed actions.
- Accept, defer, reject or reassign a suggested task with a recorded rationale.
- Record action taken and outcome, feeding operational evaluation without treating the model's own alert as ground truth.

### Clinical supervisor / service manager
- Monitor workload, overdue follow-ups, capacity, fairness of allocation and service-level outcomes using minimum-necessary aggregate views.
- Rebalance caseloads according to competence, availability, continuity, urgency and local rules.
- Audit why a case or task was prioritised and who made the final decision.
- Never use an unvalidated score alone for punitive workforce decisions or to deny access to care.

## Product modules and contracts

| Module | Required output | Must not do |
|---|---|---|
| Longitudinal clinical data | Source-linked timeline with event time, ingestion time, provenance, consent/access and missingness | Overwrite source history with summaries |
| Outpatient deterioration engine | Versioned risk estimate for a defined outcome/horizon, calibration, uncertainty, evidence and freshness | Call a score a diagnosis or crisis determination |
| Behavioural change engine | Baseline-relative change signals with modality, quality, time window and alternative explanations | Infer illness from one phrase, response latency or message length alone |
| Explainability/evidence | Reproducible features, source links, contradictory evidence and limitations | Expose hidden chain-of-thought or unsupported causal claims |
| Patient accompaniment | Agreed action, self-regulation support, feedback and human escalation route | Coerce, shame or silently escalate based solely on opaque inference |
| Workforce coordination | Prioritised task queue, eligibility/availability matching, human override and audit | Automatically diagnose, discharge, restrict or allocate solely by score |
| Model governance | Dataset/model versioning, temporal validation, monitoring, rollback and incident tracking | Train on unreviewed outcomes or leak PHI to telemetry |

## Alert semantics

Separate these concepts in APIs and UI:
- **Observed fact:** directly present in a source, with provenance.
- **Change signal:** measured deviation from an explicit baseline; not itself a clinical risk.
- **Predicted outcome:** probability/score for a prespecified outcome and horizon, only when a validated model is deployed.
- **Clinical urgency:** determined by the existing approved safety pathway and qualified human review.
- **Care task priority:** operational ranking that includes urgency, time sensitivity, expected benefit, continuity, competence and capacity.

If no validated predictive model is available, show change signals and evidence only. Do not fabricate a probability or label the result “low risk.”

## Minimum acceptance criteria for the integrated product
- Each displayed inference has source provenance, event/window times, model/version, uncertainty, missingness and consent status.
- Patient baseline is personal and versioned; population thresholds do not silently replace it.
- A missing/late source cannot be treated as a normal value.
- Every alert can be acknowledged, contextualised, escalated or dismissed by an authorised person with an audit record.
- Every suggested care task has an owner, due window, priority rationale and completion/outcome state.
- The last validated model remains active if a new build fails.
- Clinical data and historical versions are preserved.
- The app remains usable when an LLM/provider is unavailable.
- No predictive performance claim is made until the defined validation gates have been met.

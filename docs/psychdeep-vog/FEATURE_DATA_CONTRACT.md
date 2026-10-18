# Longitudinal feature and event data contract

## Purpose
Define the minimum semantic contract for predictive features without forcing a production schema change. Existing Supabase schema and source records remain authoritative. Map current tables to this contract in an inventory first; any future schema additions require a separate reviewed, additive migration.

## Event envelope
Every candidate event/observation should be representable as:
- stable source ID and source type;
- patient-scoped subject ID (never a human-readable identity in telemetry);
- event time, recorded/ingested time and timezone/precision;
- value or a reference to protected content; unit and coding system when applicable;
- provenance/source location and transformation/feature version;
- observed / reported / prescribed / dispensed / confirmed status as appropriate;
- quality flags, missingness reason and uncertainty;
- consent scope/version and access-policy context;
- correction/supersession link rather than destructive history rewrite.

Use pseudonymous identifiers in analytical datasets. Keep re-identification keys separate and access-controlled.

## Candidate feature registry
Each feature requires a stable name, plain-language definition, source mapping, unit/range, aggregation window, missingness semantics, quality checks, permitted purpose, consent basis, transformation version, known confounders, validation evidence and owner.

| Domain | Example feature | Critical semantic rule |
|---|---|---|
| Medication | Medication change, supply gap, PDC/MPR | A prescription is not proof of dispensing or ingestion; calculate adherence only when denominator and coverage are valid |
| Service use | Cancelled appointment, unscheduled contact, urgent-care event | Define source completeness; a missing encounter feed is not zero use |
| Diagnosis | New/removed/changed coded diagnosis | Coding reflects documentation and practice, not necessarily a true change in illness |
| EMA | Mood, sleep, craving, functioning, self-efficacy scales | Preserve instrument, version, timestamp, response scale and missing response |
| Sleep/circadian | Self-reported or consented wearable-derived sleep timing/duration | Identify measurement method; night work, caregiving, device non-use and time zones can confound |
| Language | Text-derived semantic/style features | Store feature summaries and provenance where possible; raw text remains protected and consent-scoped |
| Interaction | App response interval, check-in completion, text length | Usage behaviour is not a symptom by itself; do not punish non-response or infer deterioration from access gaps alone |
| Protective/contextual | Support, coping action, agreed plan | Preserve patient/clinician attribution and date; distinguish reported from independently verified |

## Missingness and observation process
Never impute missing clinical/contact/EMA data as normal or zero by default. Keep separate indicators for “not collected,” “not applicable,” “not shared/consented,” “source unavailable,” “late,” “invalid” and “unknown.” Model the observation process explicitly where appropriate. Absence of a digital trace must not be interpreted as evidence of deterioration or stability without validated context.

## Time and leakage
Keep event time distinct from database creation time. Feature windows must be anchored to a prediction cutoff; use only information available at that cutoff. Track late-arriving corrections and prevent post-outcome information from leaking into training.

## Consent and privacy
- Verify purpose-specific consent before feature generation and before external processing.
- Stop new optional digital/language processing after withdrawal and propagate the state to queues/caches.
- Apply retention and erasure obligations according to documented legal/clinical policy; withdrawal is not implemented by silently rewriting a clinical record that must be retained.
- Minimise raw-text copies; avoid raw text, prompts, model outputs and patient IDs in logs.
- Enforce role/assignment-based access for professional views and least-privilege access for research extracts.

## Registry acceptance criteria
No feature enters training or production inference without a documented definition, valid source mapping, quality/missingness semantics, purpose/consent check, leakage audit and owner sign-off. Unmapped fields remain excluded rather than guessed.

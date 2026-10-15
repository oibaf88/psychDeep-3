# Clinical validation plan

## Intended use and boundaries
Memory is a provisional, source-linked aid to longitudinal review and session preparation. It is not a diagnosis, risk score, treatment recommendation or autonomous clinical decision. Deterministic safety/risk systems remain independent.

## Validation dimensions
1. **Source fidelity:** every claim links to valid source IDs; no invented references; quotations remain distinct from interpretations.
2. **Temporal fidelity:** order, duration, turning points, time zones, late-arriving records and changes in context are handled correctly.
3. **Epistemic separation:** user report, professional report, third-party report, system observation and model hypothesis remain distinct.
4. **Contradictions and corrections:** conflicting reports are preserved with uncertainty; explicit corrections supersede only the appropriate derived interpretation, never erase source history.
5. **Coverage and omissions:** all source batches are accounted for; omissions and input limits are explicit.
6. **Stability:** identical source snapshot + prompt/schema/model version yields reproducible version metadata and idempotent persistence.
7. **Safety:** no diagnostic or risk claims are inferred by the memory model; consent revocation blocks further processing; access follows assignment/role.
8. **Human usability:** clinicians can inspect evidence and limitations, correct/contextualise via an audited annotation, and distinguish stale from current memory.

## Evaluation design
- Use synthetic or properly de-identified fixtures; do not copy production patient text into test logs.
- Establish a clinician-reviewed gold set with source references and explicit uncertainty labels.
- Double-review a sample; record agreement and adjudication for factuality, temporal ordering, unsupported inference, contradiction handling and clinical usefulness.
- Track per-version prompt/schema/model provenance, test-set version, evaluation date and reviewer role.
- Define acceptance thresholds with clinical stakeholders before claiming validation. Do not invent thresholds after seeing results.
- Separate technical correctness, content quality and clinical outcome evaluation; success in one does not prove the others.

## Release gates
No claim of clinical validation until a reviewed protocol, representative dataset, pre-specified metrics, independent review and documented results exist. Any model/prompt/schema change affecting clinical interpretation requires regression evaluation and clinical review.

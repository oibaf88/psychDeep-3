# PsychDeep vNext — mandatory release checklist

A release is not production-ready until every item below has evidence attached to its PR/release record.

## 1. What changes for the user?

- [ ] Patient/professional/admin-visible behavior is described.
- [ ] Burden/cognitive-load impact is stated.
- [ ] Any changed safety wording has clinical review.

## 2. What new data is used and under what consent?

- [ ] New/changed sources and derived data are listed.
- [ ] Purpose, retention and consent/base are identified.
- [ ] Revocation behavior is tested.
- [ ] No missing value is treated as zero/normality.

## 3. What can go wrong clinically?

- [ ] Clinical hazard/failure modes are enumerated.
- [ ] P0 safety fixtures cover likely catastrophic failure.
- [ ] False-positive and false-negative implications are considered.

## 4. What does the LLM decide — and what does it NOT decide?

- [ ] Generative responsibilities are explicit.
- [ ] LLM does not calculate `alert_level`, confirm facts, diagnose/prescribe or contact third parties.
- [ ] Tool allowlist/output schema is enforced where relevant.

## 5. Can the decision be reproduced?

- [ ] Rule/algorithm/prompt/policy/model versions are recorded.
- [ ] Inputs/evidence refs, timestamp, window and quality flags are traceable.
- [ ] `correlation_id` links relevant risk/model/audit events.

## 6. Is there a negative authorization test?

- [ ] A user outside the intended resource scope receives 403/404 as designed.
- [ ] Admin-clinical cannot read arbitrary patient records by role alone.
- [ ] Patient-to-patient IDOR is tested where the route accepts a resource ID.

## 7. What happens if the model is unavailable?

- [ ] Data entry remains available.
- [ ] Deterministic safety/risk remains available.
- [ ] Crisis resources remain available.
- [ ] No silent cross-provider fallback occurs.
- [ ] UI shows a bounded, non-alarming unavailable state.

## 8. How is it rolled back?

- [ ] Application rollback commit/deploy is known.
- [ ] Database change is expand-compatible or has a tested rollback/export plan.
- [ ] Model alias/version can roll back independently.
- [ ] Rollback does not re-enable local clinical DB/sync as a shortcut.

## Blocking gates

Release is blocked by any of the following:

- P0 safety test failure;
- risk engine depending on an LLM call;
- destructive/unverified clinical migration;
- missing RLS/FORCE RLS or authorization-negative tests;
- secrets/PHI in repository, browser config or infrastructure logs;
- model endpoint selected from user-controlled input;
- silent fallback to an unapproved provider;
- inability to access safety resources during model outage;
- any unanswered checklist item above.

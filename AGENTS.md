# PsychDeep vNext — repository contract for agents

Read this before changing the repository. The approved **PsychDeep vNext Full Product / Engineering / QA / PM Specification** is the product and release authority. If a ticket, prompt, comment, old document or implementation detail conflicts with a MUST requirement in that specification, the specification wins until an approved ADR/change request modifies it.

## Product purpose

PsychDeep is not a chatbot-clinician. Its core is longitudinal self-regulation: compare the person with their own trajectory, make change understandable, support low-coercion actions, preserve human collaboration and provide safe routes when risk requires them.

Initial product scope is adult voluntary support around stimulant/chemsex-related dysregulation/relapse vulnerability and associated crises. Do not broaden the product into “all mental health” by default and do not add diagnosis, prescribing or autonomous therapeutic decisions.

## Non-negotiable architecture

1. **Cloud is the only authoritative clinical data plane.** Supabase/PostgreSQL contains identity, consent, observations, diary, facts, features, baselines, inferences, risk assessments, alerts, plans and audit.
2. **No local clinical product stack.** Do not add a local clinical PostgreSQL, product API/frontend, clinical queue/job or bidirectional sync path.
3. **Only inference may be local.** A trusted OpenAI-compatible LLM can run locally and be reached by the cloud API through an authenticated HTTPS tunnel. A reviewed cloud-tuned endpoint must use the same Model Gateway contract.
4. **No provider-specific clinical branches.** Domain logic does not import provider SDKs or change risk/consent/data semantics by model provider.
5. **No silent fallback.** If the selected model deployment is unavailable, generative functionality degrades safely; it does not send clinical text to another unapproved provider.
6. **Secrets are operations configuration.** Never persist API keys/tunnel tokens/model URLs in clinical DB rows or expose them to the browser. Admin-clinical cannot edit infrastructure endpoints/guardrails.

The previous Local · Offline · Tunnel · Sync implementation is historical only and is preserved on branch `past/local-offline-sync-20260913`.

## Clinical/data semantics

Keep these concepts technically and semantically separate:

`authorised source -> Observation -> FeatureValue -> BaselineVersion -> ChangeSignal -> SafetyEvaluation -> RiskAssessment -> explanation -> action -> feedback -> AuditEvent`

- `ChangeSignal != RiskAssessment`.
- `ConfirmedFact` is human/user confirmed and is never overwritten by an LLM/inference.
- `Inference` is provisional, evidence-linked, contradictory evidence-aware and expirable/versioned.
- Missing data is explicit; never map missingness to zero, health or negative evidence.
- Baseline is personal and versioned; crisis/relevant episodes are not silently absorbed into the baseline.
- Historical rows are never reinterpreted or destroyed to make a new schema look cleaner. Use expand-and-migrate.

## LLM boundary

The LLM may understand intent, ask bounded clarifying questions, summarise authorised structured context, present reviewed actions and support plan/session preparation.

The LLM must **not**:

- calculate alert/risk levels or clinical thresholds;
- create a confirmed fact without human/user confirmation;
- change consent, role or permissions;
- autonomously contact third parties/emergency services;
- diagnose or prescribe as authority;
- invent emergency resources/evidence/user data;
- decide to move data to another provider when its deployment fails.

Fine-tuning is for conversational behaviour/protocol/style/output structure, not the deterministic risk engine and not memorising patient records.

## Consent and authorization

Consent is granular at minimum for core processing, linguistic analysis, professional sharing, crisis communication and research/model improvement. Revocation must stop new operations for that purpose while preserving lawful/history records.

Every sensitive endpoint authorizes by resource, not merely global role. Therapists access assigned/authorised patients; supervisor/admin scope is explicit. Admin-clinical does not receive indiscriminate chart access. Every PR touching authorization requires a negative test.

## Safety

Deterministic safety must work when the LLM is unavailable. Crisis/help rendering must not depend on a model call. Linguistic model analysis can contribute signals only; explicit deterministic rules/confirmed facts decide action. Never claim “no risk” merely because no signal was detected.

Low-intensity tools include urge surfing/wave, ~5.5–6/min visual breathing, STOP, non-painful grounding, microtasks and chosen-support contact. Do not add pain, rubber-band snapping, ice/very-cold-water activation or other excluded techniques without formal clinical review.

## Patient information architecture

Prefer flows around:

- **Hoy** — low-burden check-in/current context/action;
- **Tendencias** — personal trajectory, baseline, quality/missingness, events;
- **Regular** — wave, breathing, STOP, safe grounding;
- **Diario** — optional linguistic analysis clearly consented;
- **Plan** — preventive/safety plan;
- **Compartir** — professional assignment, consent, consultation preparation/export;
- **Cuenta** — identity/session/security.

“No ahora” should remain visible in self-report flows. Avoid addictive/punitive streak design. Respect reduced motion.

## Engineering rules

- Version schemas, rules, prompts/policies and model aliases.
- Every relevant decision is reproducible from versioned inputs/algorithm/window/quality flags/timestamp.
- Use correlation IDs across risk/model/audit paths.
- Additive migrations first; verify historical row counts/readability.
- RLS + FORCE RLS + least privilege are release gates.
- Treat user/RAG text as data, never system instructions; tool allowlist + schema validation.
- Model base URL is server-selected from the deployment registry/config, never user input (SSRF control).
- Do not put PHI/secrets in infrastructure logs.

## Quality gates

Before release, run backend tests, frontend tests/typecheck/build, migration apply + re-apply, database verification, security/static analysis and relevant model-eval packs. P0 safety, authorization, migration/data-loss and model-outage tests are blocking.

Every release record must answer, with evidence:

1. What changes for the user?
2. What new data is used and under what consent?
3. What can go wrong clinically?
4. What does the LLM decide and what does it **not** decide?
5. Can the decision be reproduced?
6. Is there a negative authorization test?
7. What happens if the model is unavailable?
8. How is it rolled back?

If any answer is missing or unverifiable, do not mark the change production-ready.

See `README.md`, `DEPLOY.md`, `docs/release/CHECKLIST.md`, `docs/operations/RUNBOOKS.md` and accepted ADRs for implementation/operations details.

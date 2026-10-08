# PsychDeep vNext — progressive implementation contract for agents

Read this file before changing the repository. It is not a generic contributor guide: it is the live implementation contract for moving PsychDeep from the historical product toward the approved **PsychDeep vNext Full Product / Engineering / QA / PM Specification** without pretending that foundations, schemas or endpoints are already equivalent to finished user value.

The approved vNext specification remains the product authority. This file adds a **progress ledger** so agents can see what has already been achieved, what remains partial, what is still missing, and why PsychDeep must not yet be described as fully aligned with vNext.

If a ticket, prompt, old document, agent suggestion or implementation detail conflicts with a MUST requirement in the specification, the specification wins unless a later explicit product-owner decision or approved ADR/change request supersedes it. When that happens, document the exception here and in an ADR rather than silently drifting.

## How to maintain this file

This document is deliberately cumulative.

- **Never delete a completed objective merely because it is done.** Mark it completed with `[x]` and strike through the objective using `~~...~~`.
- Keep the reason/evidence showing why it was considered complete.
- Use `[~]` for **partial / transitional** work. Do **not** strike it through.
- Use `[ ]` for work not yet achieved.
- Do not mark an item complete because a table, endpoint, route, test stub or screen shell exists. Completion means the intended user/clinical/operational behaviour is actually present and the relevant acceptance evidence exists.
- If an item regresses, remove the strike-through and return it to `[~]` or `[ ]`, with a short explanation.
- Every PR that materially changes vNext scope SHOULD update this ledger.

Status legend:

- `[x] ~~objective~~` = achieved and retained for traceability.
- `[~] objective` = partially implemented / compatibility bridge / insufficient evidence.
- `[ ] objective` = not yet achieved.

## Product north star — do not mark complete until the product visibly behaves this way

PsychDeep is **not** a chatbot-clinician. Its purpose is longitudinal self-regulation: compare a person with their own trajectory, detect meaningful change without conflating change with clinical risk, explain why the system thinks something changed, support proportionate low-coercion actions, preserve human collaboration, and provide safe routes when deterministic safety criteria require them.

The final product is aligned with vNext only when all of the following are true as an integrated user experience, not merely as backend infrastructure:

- [ ] The product revolves around the individual longitudinal trajectory rather than isolated scores or a chatbot conversation.
- [ ] Relevant change is explainable to the user: evidence, uncertainty, contradictions, missingness and baseline context are understandable.
- [ ] The user can add context, correct interpretations and reject/postpone suggested actions without deleting historical signals.
- [ ] Self-regulation tools are part of a coherent feedback loop: signal -> explanation -> one proportionate action -> feedback/usefulness -> longitudinal learning.
- [ ] Clinical safety remains independent of the LLM and remains functional when the selected model is unavailable.
- [ ] Human collaboration is integrated: assigned professionals can see an authorised longitudinal view, prepare sessions, understand evidence/limits and feed outcomes back into the record.
- [ ] The patient experience is organised around **Hoy / Tendencias / Regular / Diario / Plan / Compartir**, with low cognitive burden and a persistent route to help.
- [ ] Clinical data storage remains available in the cloud, while inference may run on approved mobile-local, local-tunnel, cloud-tuned or commercial deployments without changing risk, consent, data or audit semantics. Mobile-local inference may persist an offline encrypted client queue before outbound synchronization.
- [ ] Release, rollback, observability, security, privacy and model governance are demonstrably operational rather than only documented.

**Current overall state:** PsychDeep is in a **vNext foundation / transition release**, not a completed vNext product. The largest completed changes are architectural and therefore mostly invisible to end users. The patient and professional value loops remain substantially incomplete.

## Progressive migration strategy

Do not rebuild the application from scratch. Preserve useful existing FastAPI/React/Supabase/risk-engine behaviour and migrate incrementally. The order is intentional: foundations first, then canonical longitudinal behaviour, then patient/professional product value, then model/research scale.

Historical baseline for the vNext transition: repository `oibaf88/psychDeep-3`, master commit `3d286e7083a9d493a0a3c7215a7f6fe59b9032a2`.

The historical Local · Offline · Tunnel · Sync implementation is preserved on branch `past/local-offline-sync-20260913` and is not a product path.

## Gate ledger

### G0 — Baseline lock

- [x] ~~Freeze the historical implementation baseline and preserve the former local/offline/sync architecture.~~
  - Evidence: baseline commit is recorded; historical branch exists.
  - Why complete: agents can identify the starting state and recover the retired architecture without keeping it in production.

### G1 — Cloud-only foundation

- [x] ~~Make Supabase/PostgreSQL the only authoritative clinical data store.~~
- [x] ~~Remove the local clinical PostgreSQL/API/frontend product path.~~
- [x] ~~Remove SymmetricDS and bidirectional clinical sync from the active product path.~~
- [x] ~~Keep only the local LLM server/tunnel as an optional local component.~~
- [x] ~~Rewrite deployment documentation around cloud API/web + Supabase + optional model tunnel.~~

Why this gate is considered substantially achieved: the product no longer depends on a second local clinical state. Local DB/sync scripts and the offline compose path were removed from active master, while the model-only tunnel remains available.

What this gate **does not** prove: it does not by itself make the patient experience longitudinal, explainable or therapeutically useful.

### G2 — Canonical longitudinal model

- [x] ~~Introduce canonical entities for Observation, FeatureDefinition/FeatureValue, BaselineVersion, ChangeSignal, ModelRun, Inference, InterventionEvent and model deployment metadata.~~
- [x] ~~Backfill legacy check-ins/diary/baseline/signal/model-trace data additively without destroying history.~~
- [x] ~~Dual-write new check-ins/diary content into canonical observations while legacy compatibility remains.~~
- [~] Make the complete operational analytics path run through `Observation -> FeatureValue -> BaselineVersion -> ChangeSignal` rather than legacy calculations.
  - A check-in now refreshes that canonical trajectory in the same request. Hoy reads that persisted ChangeSignal for the change-versus-baseline reading, apart from `safety.alert_level`. Authorised professional summary and dossier reads show the same ChangeSignal beside risk. The professional structural score and `RiskAssessment` still come from the legacy baseline and the risk engine.
  - Completion criterion: canonical feature computation, baseline eligibility/versioning and change detection are the actual source for vNext state and explanations, with tests proving reproducibility.
- [~] Make personal baseline behaviour fully conform to vNext semantics.
  - Current gap: canonical baseline records exist and can be read, but the complete lifecycle (eligibility, provisional status, exclusions, recalibration/versioning, quality/missingness) is not yet the primary end-to-end product behaviour.
- [x] ~~Separate `ChangeSignal` from `RiskAssessment` everywhere in API **and UI**.~~
  - Evidence: patient `GET /api/v1/state` (PR #143) and Hoy (PR #151, merged) keep `longitudinal` apart from `safety.alert_level`. Authorised professional summary and dossier (PR #153) return persisted `BaselineVersion` + `ChangeSignal` beside `latest_alert_level` / `RiskAssessment`. `GET /api/v1/review/weekly` now returns the same split. Roster, copilot picker, alert list, structural-score chart and the risk card label the engine's similarity band as a risk-engine input. The copilot dossier and Agent 1 safety posture name change and risk separately. A missing ChangeSignal stays null / `insufficient_data` and is not serialised or rendered as zero or “sin riesgo”.
  - Tests: `tests/test_vnext_change_risk_separation.py`, `tests/test_professional_longitudinal.py`, `tests/test_clinical_view.py`, `tests/test_clinical_copilot.py`, `tests/test_agent1_context.py`, and the frontend suites `ChangeRiskSurfaces`, `ProfessionalDashboard`, `professionalChange`, `PatientDashboard`, `longitudinalReading` and `PatientTimelinePages`.

Why G2 is **not complete**: the operational analytics path and `GET /api/v1/state` now use canonical baseline and change signals, and ChangeSignal is presented apart from RiskAssessment in the API and UI. Personal baseline lifecycle semantics are still partial, and ChangeSignal is not the source of the professional structural score or the risk engine.

### G3 — Safety vNext

- [x] ~~Keep deterministic risk/safety logic independent from the LLM.~~
- [x] ~~Materialise explicit high-salience first-person safety declarations without requiring a model call.~~
- [x] ~~Ensure model outage does not remove core storage or deterministic safety processing.~~
- [x] ~~Keep `ConfirmedFact` semantically separate from provisional LLM inference.~~
- [~] Version all safety protocols/resources and prove every P0 scenario against the final vNext safety suite.
- [~] Add/complete output validation that blocks or replaces unsafe LLM output with deterministic structured support and logs the event.
- [ ] Complete formal clinical sign-off for vNext safety thresholds/protocol behaviour.
- [ ] Complete the full model regression/gold safety suite including GHB/GBL withdrawal, ambiguous language, clear crisis, hallucination traps, prompt injection and boundary requests.

Why G3 is **not complete**: independence from the LLM is materially improved, but the full specified safety validation package and clinical sign-off are not yet evidenced.

### G4 — Patient value loop

This is the largest current product gap. Do not confuse navigation changes with completion.

- [~] **Hoy — redesign around current state and one useful next action.**
  - Hoy reads canonical longitudinal state for change versus the personal baseline, with explicit missingness, and keeps crisis/help plus “No ahora”. The first view is an open page: a large comparison, a fact row, one default action, then an open check-in. The 30-day chart stays, and the feature-by-feature reading sits under it. That action is not yet tied to the change explanation or to feedback.
  - Required completion: low-burden check-in, current state, change vs personal baseline, data quality/missingness, explanation, at most one default suggested action, persistent crisis/help access and “No ahora”.
- [~] **Tendencias — longitudinal explanation.**
 - A new page exists and reads timeline, baseline and ChangeSignal data. Calculated bands and an uncalculated comparison now use plain-language copy; the raw `insufficient_data` code stays off the page.
 - Required completion: evidence, uncertainty, contradictions, missingness, contextual events and a fuller “why this changed” explanation.
- [ ] **Relevant-change interaction flow.**
  - Required: “tu patrón reciente puede estar cambiando” -> why/evidence -> optional contextual explanation -> proportionate action -> professional route when appropriate -> feedback recorded without deleting the signal.
- [ ] **Weekly review UI.**
  - Backend endpoint exists, but there is no complete patient-facing weekly review experience.
  - Required: trends, protective factors, possible triggers, contradictions, questions for consultation and user correction/context.
- [~] **Regular — Wave / breathing / STOP / grounding as a coherent intervention loop.**
  - Legacy tools exist.
  - Required completion: vNext UX, low cognitive load, reduced-motion handling and feedback/usefulness recording linked to the triggering context/action.
- [~] **Plan — safety/prevention plan UX.**
  - Existing plan retained.
  - Required completion: warning signs, coping steps, supports, professional contacts, environment, one-tap access and integration with current state/change flows.
- [~] **Diario — optional linguistic analysis with explicit consent.**
  - Separate consent enforcement exists.
  - Required completion: clearer UI explanation of what is analysed, what remains factual vs inferred, correction controls and graceful behaviour after revocation.
- [~] **Compartir — user control and consultation preparation.**
  - A new page links assignments, consent, trends and facts.
  - Required completion: actual consultation preparation summary/export/share package, correction review and clear authorised-recipient scope.
- [ ] **Confirmed fact / inference correction as a first-class patient flow.**
- [~] **Clinical memory stays immutable for the patient.**
  - Chat and diary can commit a discourse fact, a psychological reading and a versioned formulation when linguistic-analysis consent is current. The patient cannot edit or delete that record, and the formulation is not shown in the patient account. User-declared `ConfirmedFact` rows keep their existing correction flow. A failed memory read releases the database transaction, so the chat reply still returns.
- [ ] **Intervention feedback as a visible product loop.**
  - Canonical feedback endpoint/data exists; the product experience is not yet integrated.

Why G4 is **not complete**: the patient still experiences much of the old application. New routes and backend contracts exist, but the core vNext value loop has not yet replaced the historical dashboard behaviour.

### G5 — Professional / human collaboration loop

- [~] Preserve assignment-based authorised access and professional roles.
  - `admin_clinical` can read each patient's assignment lifecycle, split into pending and done, from the roster, Asignaciones and the selected user. That read stays free of clinical signals, alerts and dossier access. Negative tests cover a patient or therapist using the same filter to read someone else's links. Chart access for `admin_clinical` stays closed.
- [~] Preserve longitudinal patient history access for authorised clinicians.
- [~] Assigned clinicians can read clinical memory and receive a separate in-app attention notice.
  - The patient chart has a Memoria y lectura section: formulation, discourse facts, readings, professional notes and open notices. Notices are deterministic rules over stored memory. They do not write `ProfessionalAlert` or change `alert_level`. `admin_clinical` remains excluded. Negative tests cover an unassigned therapist and `admin_clinical`.
- [ ] Redesign the professional patient view around longitudinal trajectory, baseline, ChangeSignals, evidence, uncertainty, assessment trace, interventions and outcomes.
- [ ] Implement a structured **session preparation summary** derived from authorised structured data, with evidence and limitations.
- [ ] Allow professionals to add context and confirm/correct facts with versioned history rather than silent edits.
- [ ] Integrate alert outcome feedback and intervention feedback into the longitudinal record.
- [ ] Demonstrate resource-level authorisation for every professional clinical view, including negative assignment tests.

Important current reality: the main professional dashboard remains essentially the historical component; therefore G5 must not be marked complete merely because backend authorisation already exists.

### G6 — Replaceable Model Gateway

- [x] ~~Introduce provider-neutral Model Gateway abstractions for approved deployments.~~
- [x] ~~Support an OpenAI-compatible local/tunnel deployment without changing clinical domain logic.~~
- [x] ~~Keep credentials server-side and out of clinical DB rows/browser payloads.~~
- [x] ~~Prohibit silent cross-provider fallback when a selected model fails.~~
- [x] ~~Restore explicit audited Anthropic/local runtime selection for `admin_clinical`.~~
- [x] ~~Enable `LLM_ALLOW_RUNTIME_OVERRIDE=true` for the intended runtime-switch workflow.~~
- [~] Add a true reviewed `cloud-tuned` deployment profile backed by an actually hosted/tuned model.
- [ ] Prove behavioural/contract equivalence across local-tunnel and cloud-tuned profiles with model-gateway contract tests and fail-safe tests.

#### Explicit product-owner override to the original vNext spec

The original master specification stated that only Ops/ML promotion should change production aliases and that the clinical admin should not switch models/endpoints from the UI. A later explicit product-owner decision **supersedes that restriction for the current product**:

- `LLM_ALLOW_RUNTIME_OVERRIDE=true` is intentional.
- Only `admin_clinical` may explicitly switch between approved Anthropic and approved local/OpenAI-compatible deployments from the UI.
- Patient, therapist and supervisor must not mutate provider configuration.
- Switching must be authenticated, audited and must never expose credentials.
- There is still no silent fallback.
- The clinical admin's saved Codex / ChatGPT or Anthropic connection is the inference connection for patient chat, analysis and the professional copilot. A local LM Studio connection stays on the account that saved its own key. Patient chat must not keep using an old tunnel selection after Codex or Anthropic is saved.

Agents must not “fix” this back to read-only model settings unless a later product-owner decision/ADR reverses it.

### G7 — Cloud fine-tuned candidate / RAG / model governance

- [~] Canonical model-run/deployment metadata exists as a foundation.
- [~] Implement curated RAG content registry with source/version/reviewer/evidence level/contraindications/review date.
  - Current foundation: backend-only draft/approve/retire registry, explicit reviewer and review date, one active version per target, contraindication-aware `GET /api/v1/knowledge/retrieve`, and negative role tests. That retrieve route does not call a model.
  - Current injection: `agent1_context._knowledge_block` appends every `active` item whose `review_due` is null or still current into Agent 1's bounded context (PR #137). It does not retrieve by turn, population, locale or topic, and it does not apply contraindications.
  - Current gap: reviewer workflow in the product UI, clinical validation, prompt-injection tests, content-version provenance on `ModelRun`, and rollback rehearsal remain incomplete. Do not describe this as a governed retrieval pipeline.
- [ ] Create de-identified/reviewed dataset pipeline for tuning; never fine-tune patient memory into the model.
- [ ] Train or adapt the approved cloud candidate for behaviour/style/schema/tool-use only, not risk calculation.
- [ ] Add reproducible model card, dataset manifest, base/tokenizer/artifact checksums, code/container version, seed, hyperparameters and metrics.
- [ ] Run model evaluation gates: schema adherence, policy adherence, crisis handling, unsupported claims, Spanish quality, over-refusal, tool use, latency/cost and regression.
- [ ] Progress candidate through experiment -> evaluated -> clinically reviewed -> shadow -> canary -> production only with evidence.

Why G7 is **not complete**: a replaceable gateway is not the same thing as a tuned cloud model or an evaluated promotion process. Active knowledge text can reach Agent 1, but that copy is an unfiltered context append, not targeted retrieval with contraindication filtering, content-version audit or a rehearsed rollback.

### G8 — Pilot readiness

- [ ] End-to-end production observability and alerting are active and reviewed.
- [ ] Backup/restore has been rehearsed, not only documented.
- [ ] DB migration rollback/restore path has been exercised on a production-like snapshot.
- [ ] Model alias rollback and RAG-content rollback have been rehearsed.
- [ ] Privacy/security review covers provider data processing, retention, region/DPA and secondary-use constraints.
- [ ] Accessibility critical issues are resolved against the target WCAG level.
- [ ] There are zero open P0/P1 defects under the vNext release matrix.
- [ ] All MUST requirements have linked automated/manual evidence.
- [ ] Clinical Safety, Engineering, QA, Ops and Product have an explicit go/no-go package.

Why G8 is **not complete**: successful CI and a healthy Render deployment are necessary engineering evidence, but they are not equivalent to pilot readiness or clinical validation.

## Completed architectural changes retained for traceability

The following changes were made during the transition and must not be casually undone:

- [x] ~~Removed `docker-compose.offline.yml` from the active product path.~~
- [x] ~~Removed `ops/local/*` local clinical-stack scripts.~~
- [x] ~~Removed `ops/sync/*` SymmetricDS configuration/scripts.~~
- [x] ~~Added model-only tunnel tooling under `ops/model/`.~~
- [x] ~~Added additive vNext Supabase migrations and verification SQL.~~
- [x] ~~Retired stored runtime LLM API keys from DB-backed configuration.~~
- [x] ~~Disabled/retired active sync privileges and schema paths.~~
- [x] ~~Added FORCE RLS/backend-only policy expectations for canonical vNext tables.~~
- [x] ~~Added canonical observations and dual-write compatibility for check-ins/diary.~~
- [x] ~~Added vNext API façade for state, baseline, changes, analytics, safety, support, weekly review, model status and feedback.~~
- [x] ~~Added `TrendsPage` and `SharingPage` plus patient navigation around Hoy/Tendencias/Regular/Diario/Plan/Compartir.~~
- [x] ~~Added deterministic safety-text materialisation independent of model availability.~~
- [x] ~~Added Model Gateway and runtime provider-switch regression coverage.~~
- [x] ~~Added release checklist, runbooks and cloud-first/model-gateway ADR documentation.~~
- [x] ~~Added clinical long-term memory for models: discourse facts, versioned formulations and therapist attention notices separate from risk (ADR-0002).~~
  - The patient cannot edit or delete this memory. World claims inside speech stay unconfirmed. G4 and G5 stay partial: the patient does not see the formulation, and the professional home is still the historical dashboard.

These completed items are **foundations**. They are not sufficient reasons to call G4/G5/G7/G8 complete.

## Backlog mapping — never delete achieved items

### P0 — architecture / safety / security blockers

- [x] ~~PM-001 Decommission product path for local frontend/backend/Postgres/SymmetricDS.~~
- [x] ~~PM-002 Create Model Gateway and approved deployment abstraction.~~
- [~] PM-003 Canonical Observation/Feature/Baseline/ChangeSignal schemas **and full operational pipeline**.
  - Progress: analytics/run (PR #128) and `GET /api/v1/state` (PR #143) use the canonical Observation → FeatureValue → BaselineVersion → ChangeSignal path. Hoy renders that `longitudinal` payload for change-versus-baseline framing. Baseline lifecycle completeness remains open, and the professional structural score is still the risk engine's similarity input, shown apart from ChangeSignal, so this item stays partial.
- [x] ~~PM-004 Separate change signal from RiskAssessment in API **and UI**.~~
  - Evidence: patient state and Hoy, authorised professional summary and dossier, weekly review, roster, copilot, alerts, and the structural-score surfaces keep change bands apart from alert levels. A missing ChangeSignal is not zero and is not “sin riesgo”. See the G2 separation item for the test list.
- [~] PM-005 Version safety protocols/resources and remove direct LLM dependency.
- [~] PM-006 Resource-level authorization matrix and comprehensive negative tests.
- [x] ~~PM-007 Split consent purposes and enforce linguistic-analysis revocation.~~
- [~] PM-008 ModelRun audit with prompt/model/policy/content versions.
- [~] PM-009 RAG curated knowledge registry foundation.
  - Progress: active, unexpired items are copied into Agent 1 context. That path is not targeted, does not apply contraindications, and `ModelRun` does not store content versions.
- [~] PM-010 Production observability and correlation IDs end-to-end.
- [ ] PM-011 Backup/restore and migration rehearsal.

### P1 — core product value

- [~] PM-012 Today dashboard redesign.
  - First vNext UI pass remains in the patient dashboard: lower-burden check-in, current-state framing, one proportionate suggested action and “No ahora”.
  - Hoy now also reads `longitudinal` from `GET /api/v1/state` for change versus the personal baseline. The first view shows one default action; the extra Tendencias card is no longer beside it. Tying that action to the change explanation and recording feedback are still open.
- [ ] PM-013 Weekly review user experience.
- [~] PM-014 Improved trend/baseline visualisation.
  - Trends now foreground personal trajectory, baseline context and reading guidance. An uncalculated comparison is described as missing data, including that a missing calculation is not evidence that things are fine.
- [ ] PM-015 Context annotation/correction.
- [~] PM-016 Intervention feedback (data/API foundation exists; UX loop missing).
- [~] PM-017 Wave/urge surfing (legacy feature exists; visual refresh applied; vNext integration incomplete).
- [~] PM-018 Breathing visual (legacy feature exists; vNext integration incomplete).
- [~] PM-019 Safety plan UX (legacy feature exists; vNext integration incomplete).
- [ ] PM-020 Professional longitudinal view redesign.
- [ ] PM-021 Session preparation summary.
- [ ] PM-022 Alert outcome feedback loop.
- [ ] PM-023 Export/share package.
- [~] PM-031 Clinical long-term memory for the models.
  - Discourse facts record what was said. Psychological readings stay inferences. Formulations are versioned L0/L1/L2. The patient cannot modify this memory. Assigned clinicians get an in-app attention notice that is not a risk alert. Embeddings, when stored, come only from the selected OpenAI-compatible deployment. A failed memory read releases the database transaction so chat still answers. This is not a governed training pipeline and does not complete G4 or G5.

### P2 — research / scale

- [ ] PM-024 Wearable connector after incremental-value study.
- [ ] PM-025 Calendar connector with privacy guardrails.
- [ ] PM-026 Change-point/sequence research.
- [ ] PM-027 Cloud fine-tuned model canary.
- [ ] PM-028 Multilingual content.
- [ ] PM-029 Research export workspace.
- [ ] PM-030 Prospective event prediction only under an approved protocol.

## Non-negotiable architecture

1. **Cloud is the only authoritative clinical data plane.** Supabase/PostgreSQL contains identity, consent, observations, diary, facts, features, baselines, inferences, risk assessments, alerts, plans and audit.
2. **No local clinical product stack.** Do not add a local clinical PostgreSQL, product API/frontend, clinical queue/job or bidirectional sync path.
3. **Only inference may be local.** A trusted OpenAI-compatible LLM can run locally and be reached by the cloud API through an authenticated HTTPS tunnel. A reviewed cloud-tuned endpoint must use the same provider-neutral inference contract.
4. **No provider-specific clinical branches.** Domain logic does not change risk/consent/data semantics by model provider.
5. **No silent fallback.** If the selected model deployment is unavailable, generative functionality degrades safely; it does not send clinical text to another provider unless an `admin_clinical` explicitly selects that provider.
6. **Runtime switching is privileged and audited.** `MODEL_DEPLOYMENT_ALIAS` defines the deployment/reset default. With `LLM_ALLOW_RUNTIME_OVERRIDE=true`, only `admin_clinical` may select Anthropic or the approved OpenAI-compatible deployment.
7. **Credentials are operations configuration.** Never persist API keys/tunnel tokens in clinical DB rows or expose them to the browser.

## Clinical/data semantics

Keep these concepts technically and semantically separate:

`authorised source -> Observation -> FeatureValue -> BaselineVersion -> ChangeSignal -> SafetyEvaluation -> RiskAssessment -> ExplanationContext -> action -> feedback -> AuditEvent`

- `ChangeSignal != RiskAssessment`.
- `ConfirmedFact` is user/human confirmed and is never overwritten by an LLM inference.
- A discourse fact records that a conversation with the model happened: the words, the channel, the time and the manner of speech. It is not a `ConfirmedFact` about the world. Saying that a medication was taken does not establish the act.
- A psychological reading is a versioned inference about why the person is speaking this way. It is not a diagnosis and not an alert level.
- Clinical memory of this kind is immutable for the patient. A professional note explains a row and does not replace it. See ADR-0002.
- `Inference` is provisional, evidence-linked, contradiction-aware and expirable/versioned.
- Missing data is explicit; never map missingness to zero, health or negative evidence.
- Baseline is personal and versioned; crisis/relevant episodes are not silently absorbed into baseline updates.
- Historical rows are never destroyed or silently reinterpreted to make a new schema cleaner. Use expand-and-migrate.
- New context may explain a historical observation/signal; it must not erase it.

## LLM boundary

The LLM may understand intent, ask bounded clarifying questions, summarise authorised structured context, explain reviewed signals/actions and support plan/session preparation.

The LLM must **not**:

- calculate alert/risk levels or clinical thresholds;
- create a confirmed fact without human/user confirmation;
- change consent, role or permissions;
- autonomously contact third parties/emergency services;
- diagnose or prescribe as authority;
- invent emergency resources, evidence or user data;
- decide to move data to another provider when its deployment fails;
- substitute model output for deterministic safety rules.

Fine-tuning is for conversational behaviour, protocol/style, structured output and tool-use — not the deterministic risk engine and not memorising patient records.

## Consent and authorization

Consent is granular at minimum for core processing, linguistic analysis, professional sharing, crisis communication and research/model improvement. Revocation must stop new operations for that purpose while preserving lawful/history records.

Every sensitive endpoint authorises by resource, not merely global role. Therapists access assigned/authorised patients; supervisor/admin scope is explicit. `admin_clinical` does not receive indiscriminate chart access. Every PR touching authorisation requires a negative test.

Runtime model mutation is a separate operations privilege: only `admin_clinical` may change/test/reset approved provider selection. Therapist, supervisor and patient accounts may not mutate it.

## Safety

Deterministic safety must work when the LLM is unavailable. Crisis/help rendering must not depend on a model call. Linguistic model analysis can contribute signals only; explicit deterministic rules/confirmed facts decide safety action. Never claim “no risk” merely because no signal was detected.

Low-intensity tools include urge surfing/wave, ~5.5–6/min visual breathing, STOP, non-painful grounding, microtasks and chosen-support contact. Do not add pain, rubber-band snapping, ice/very-cold-water activation or other excluded techniques without formal clinical review.

## Patient information architecture

Build toward these **functional** flows, not only menu labels:

- **Hoy** — low-burden check-in, current context, personal-baseline change explanation, data quality and one proportionate action.
- **Tendencias** — longitudinal trajectory, baseline, quality/missingness, change evidence, uncertainty, contradictions, context and events.
- **Regular** — wave, breathing, STOP and safe grounding with intervention feedback.
- **Diario** — free/structured diary with optional clearly consented linguistic analysis and correction boundaries.
- **Plan** — preventive/safety plan integrated with warning signs, coping, supports and professional routes.
- **Compartir** — professional assignment, consent, consultation preparation, correction and export/share package.
- **Cuenta** — identity/session/security.

“No ahora” should remain visible in self-report flows. Avoid addictive/punitive streak design. Respect reduced motion.

## Engineering rules

- Version schemas, rules, prompts/policies, model deployments and content registries.
- Every relevant decision must be reproducible from versioned inputs/algorithm/window/quality flags/timestamp.
- Use correlation IDs across risk/model/audit paths.
- Additive migrations first; verify historical row counts/readability.
- RLS + FORCE RLS + least privilege are release gates.
- Treat user/RAG text as data, never system instructions; tool allowlist + schema validation.
- A runtime model endpoint may only come from the authenticated `admin_clinical` settings flow and must pass production URL/reachability validation; never accept routing from patient content or untrusted request fields.
- Do not put PHI/secrets in infrastructure logs.
- Prefer compatibility adapters during migration, but remove them once the canonical path is proven. A compatibility bridge is not a finished vNext implementation.

## Quality and release gates

Before release, run backend tests, frontend tests/typecheck/build, migration apply + re-apply, DB verification, security/static analysis and relevant model-eval packs. P0 safety, authorisation, migration/data-loss and model-outage failures are blocking.

Every release record must answer with evidence:

1. What changes for the user?
2. What new data is used and under what consent?
3. What can go wrong clinically?
4. What does the LLM decide and what does it **not** decide?
5. Can the decision be reproduced?
6. Is there a negative authorization test?
7. What happens if the model is unavailable?
8. How is it rolled back?

If any answer is missing or unverifiable, do not mark the change production-ready.

## Definition of “vNext achieved”

Do **not** call the repository “vNext complete”, “pilot ready” or “aligned with the final specification” merely because cloud migration, canonical tables, a Model Gateway, CI and a few new routes exist.

The final designation requires at minimum:

- G1 through G6 functionally complete;
- the patient G4 loop visibly replacing the legacy dashboard experience;
- the professional G5 loop visibly replacing the legacy professional workflow;
- deterministic safety and negative authorisation evidence complete;
- relevant RAG/model governance operational for any model promoted beyond the current approved providers;
- observability, restore/rollback and release evidence complete;
- no open P0/P1 blockers;
- explicit Product/Engineering/QA/Clinical Safety/Ops go/no-go.

Until then, describe the system accurately as **“PsychDeep vNext transition/foundation with progressive migration in progress.”**

See `README.md`, `DEPLOY.md`, `docs/release/CHECKLIST.md`, `docs/operations/RUNBOOKS.md`, the approved master specification and accepted ADRs for implementation and operations details.

## Cursor Cloud specific instructions

This section is operating guidance for Cloud Agents. It does not change the product data plane: Supabase remains the only authoritative clinical store. The local PostgreSQL process below exists so agents can boot the API with `APP_ENV=local` (`create_all` plus demo seed). Do not describe that process as a supported clinical product stack, and do not apply `supabase/migrations` onto the `psychapp` database the API is using.

- The image provides Python 3.12 and Node 22. CI pins Python 3.11 and Node 20. Backend pytest and frontend vitest, `tsc`, and the Vite build were verified on 3.12 and 22.
- Backend dependencies live in `backend/.venv` (`pip install -r backend/requirements-dev.txt`). Frontend dependencies come from `npm ci` in `frontend/`.
- On boot, PostgreSQL 16, the API (`http://127.0.0.1:8000`), and Vite (`http://127.0.0.1:5173`) are started. Vite must receive `VITE_API_BASE_URL=http://127.0.0.1:8000`.
- The boot script forces `DATABASE_URL=postgresql://psychapp:psychapp@127.0.0.1:5432/psychapp` and `APP_ENV=local`. An injected `DATABASE_URL` secret is the cloud Supabase URL. Do not start the API with `APP_ENV=local` against that URL: startup calls `create_all` and can seed demo accounts into the cloud database.
- Demo patient login is prefilled in Vite dev mode. The password is `DemoPass123!` in `backend/app/seed.py`. A saved check-in shows `Check-in registrado.`
- Before `python -m pytest tests/ -q`, unset `MODEL_LOCAL_CF_ACCESS_CLIENT_ID` and `MODEL_LOCAL_CF_ACCESS_CLIENT_SECRET` when they are present without `MODEL_LOCAL_CF_ACCESS_HOST` and `MODEL_LOCAL_CF_ACCESS_REQUIRED`. That partial pair fails `tests/test_llm_endpoint.py::ProviderSelectionTests::test_local_profile_is_selectable_and_uses_its_endpoint` because `build_provider` reads live settings. With those two variables unset, the suite matches CI.
- Local-tunnel inference stays unconfigured until `MODEL_LOCAL_BASE_URL` and a complete Cloudflare Access set exist. Login, check-in, and deterministic safety do not need a model. Health then reports `model.configured: false` while `status` remains `ok`.
- The migration apply/re-apply gate is `.github/workflows/tests.yml`. It needs the Supabase role model (`supabase_admin` as superuser and a non-superuser `postgres`). Do not point that job at the local `psychapp` database.

# psychDeep-vOG

PsychDeep is a cloud-first longitudinal self-regulation platform. Its purpose is to help a person understand changes relative to their own trajectory, strengthen self-efficacy, use low-intensity regulation tools and collaborate with authorised professionals without turning an LLM into a clinician.

> **Project identity (2026-10-15):** psychDeep-vOG is the new product identity for this existing application. This is a continuity-preserving evolution, not a clean-room replacement. The existing Supabase project, `psychdeep_v12` schema, clinical source records, provenance, consent history and historical model versions remain the production source of truth. See `docs/psychdeep-vog/` for the agent contract, architecture, preservation policy, implementation plan, clinical validation and operations runbook.


The master product/engineering specification is the release authority. Approved ADRs/change requests may refine its implementation contract when product requirements are clarified.

The latest version now implements Epic E10: it incorporates a robust Professional Dashboard and selective sharing linkage management where patients and professionals can securely request, pause, resume, cancel, and end sharing assignments directly via UI.

## Non-negotiable architecture

```text
Browser
  │ HTTPS
  ▼
Render static web
  │ HTTPS/JWT
  ▼
Render FastAPI ───────────────► Supabase PostgreSQL (single clinical source of truth)
  │                                  │
  ├── deterministic safety/risk      ├── observations/features/baselines/changes
  ├── longitudinal analytics         ├── facts/inferences/plans/alerts
  ├── audit/governance               └── model runs/audit/history
  │
  └── replaceable inference boundary
       ├── local-tunnel ──HTTPS──► local OpenAI-compatible LLM (the model loaded in LM Studio)
       ├── cloud-tuned ──────────► approved private managed inference endpoint
       ├── Anthropic ────────────► approved commercial provider
       └── Codex / ChatGPT ──────► OpenAI API with the server key
```

Only the LLM inference server may be local. There is **no supported local clinical PostgreSQL, local product API/frontend, bidirectional clinical sync, or SymmetricDS path in vNext**. The historical implementation is preserved on branch `past/local-offline-sync-20260913`.

## Clinical safety boundary

- `RiskAssessment.alert_level` is produced only by the deterministic, versioned risk engine.
- An LLM can contribute an inference/signal but cannot confirm a fact, calculate the alert level, contact third parties, prescribe, diagnose or suppress a deterministic crisis response.
- Explicit first-person crisis declarations have a narrow deterministic text path so safety remains available when the selected LLM is offline.
- Confirmed facts, observations, derived features, inferences and actions remain distinct.
- Missing data is missing data; it is never silently converted to zero or normality.
- Active curated knowledge can be copied into Agent 1's read-only context as psychoeducational reference. That text does not calculate risk, confirm facts, or replace deterministic safety, and it is not turn-targeted retrieval. See [Curated knowledge](#curated-knowledge).


## Model selection

`MODEL_DEPLOYMENT_ALIAS` defines the deployment default:

- `local-tunnel`: an OpenAI-compatible model on a trusted machine, exposed only through authenticated HTTPS tunnelling when the cloud API needs it.
- `cloud-tuned`: a private/managed compatible endpoint for a reviewed tuned model.
- `commercial-approved`: approved commercial deployment profile.

The running API has personal mode on (`LLM_PERSONAL_MODE`) and `LLM_ALLOW_RUNTIME_OVERRIDE=true`. Only `admin_clinical` opens **Mis modelos** (`/settings`). Patient, therapist and supervisor accounts do not. The screen saves one connection:

- **Local** — that account's LM Studio API key, encrypted in `llm_user_preferences`. PsychDeep does not accept a model name. Inference uses the single model LM Studio reports as loaded. If several models are advertised and none is uniquely loaded, local inference stops.
- **Anthropic** — the server-side Anthropic key and model id. The blueprint sets `ANTHROPIC_CHAT_MODEL=claude-sonnet-4-6`.
- **Codex / ChatGPT** — the server-side OpenAI key and model id. The blueprint sets `OPENAI_CHAT_MODEL=gpt-5.6-luna`.

When the clinical admin saves Anthropic or Codex / ChatGPT, patient chat, text analysis and the professional copilot use that connection. A local LM Studio key stays on the account that saved it. Every save is audited and affects later model calls only. It does not change consent, storage, risk rules or historical provenance.

There is no primary/fallback provider chain. If the selected provider is unavailable, model-dependent functionality fails safely while data entry, deterministic risk/safety and crisis resources remain available. Model credentials remain server-side secrets. **Mis modelos** does not accept an endpoint URL or a model id. The tunnel URL and Cloudflare Access credentials stay in Render.

## Data migration

vNext uses expand-and-migrate. Existing `psychdeep_v12` records are never rebuilt or reinterpreted in place. Canonical tables are additive and legacy rows remain readable while endpoints move gradually:

`observations`, `feature_definitions`, `feature_values`, `baseline_versions`, `change_signals`, `inferences`, `model_runs`, `intervention_events`, `knowledge_items`, `fine_tune_runs`, `model_deployments`.

Clinical memory (ADR-0002) adds `memory_commits`, `discourse_facts`, `psych_readings`, `formulation_versions`, `memory_annotations`, `clinical_attention_notices` and `memory_embeddings`. A chat or diary turn can append a discourse fact, a provisional reading and a formulation version when linguistic-analysis consent is current. The patient cannot edit or delete those rows. Assigned therapists and supervisors read them on the chart under **Memoria y lectura**. An attention notice is not a risk alert and is not shown to `admin_clinical`. See [ADR-0002](docs/adr/0002-model-memory.md).

The migration backfills canonical compatibility rows with references to legacy sources; original clinical rows remain untouched.

## Check-in trajectory

`POST /api/v1/checkins` requires the patient role and a current grant of `data_processing` (`CORE_PROCESSING` in `backend/app/services/consent.py`). A missing grant is HTTP 403 with `Consent required for purpose: data_processing`. The handler then:

1. Stores the check-in and commits it.
2. Dual-writes `mood`, `craving`, `sleep_hours` and `self_efficacy` into `observations`. Notes become a `checkin_context` observation. That write commits separately (`record_checkin`).
3. Recomputes the canonical trajectory (`refresh_trajectory` → `run_canonical_analytics`, algorithm `canonical-structural-v3`).
4. Runs the deterministic risk engine. This step still runs when step 3 fails.

`POST /api/v1/observations` stores an observation and does not recompute the trajectory. `POST /api/v1/analytics/run` requires the same `data_processing` grant, recomputes the trajectory, and does not calculate risk. After that commit it calls `embed_change_signals` (see below). `GET /api/v1/state` only reads stored rows: `safety` is the latest `RiskAssessment`; `longitudinal` is the current `BaselineVersion` plus the newest `ChangeSignal` for each feature on that baseline. Neither read calls a model.

Parameters live in `backend/app/services/change_config.py` (`change-bands-v1-population-prior`). The same module feeds the risk engine's structural input (`structural-v3`). Stored rows keep `calibration_status = provisional_population_prior`. These bands are not a clinical sign-off; see [ADR 0003](docs/adr/0003-evidence-based-change-bands.md).

| Input | Rule |
| --- | --- |
| Recent window | the last 7 days, ending at now |
| Reference window | the 28 days immediately before the recent window; no timestamp is in both |
| Unit | mean per Europe/Madrid calendar day; several check-ins on one day count once |
| Axis eligibility | at least 5 distinct reference days with a value; otherwise `insufficient_data` |
| Craving axis | z uses `craving_inv = 10 - reported craving` (higher means less craving). `longitudinal` `display` puts craving back on the 0–10 scale the person reported |
| SD | max(personal SD of those day means, floor): 1 point for mood, `craving_inv` and self-efficacy; 0.5 h for sleep |
| Statistical band | \|z\| ≥ 1.3 `unstable`; ≥ 1.0 `transition`; otherwise `stable`. `change_value` is that z, or null when the band is `insufficient_data` |
| Raw guard | a band above `stable` also needs a raw axis change of at least 1 point (2 points to stay `unstable`) or 0.5 h of sleep. A smaller move is downgraded. The composite leaves `stable` only when at least one axis meets its transition guard |
| Composite | `structural_composite` is another `ChangeSignal`, not a risk level |

A failed refresh logs the exception type and, when available, the PostgreSQL constraint name, then rolls back the analytics transaction. The check-in and observation dual-write stay, because they were already committed. On production startup, a deterministic catch-up pass recomputes the canonical trajectory only for users whose latest numeric observation is newer than their latest `canonical-structural-v3` baseline (or who have no v3 baseline). This repairs missed refreshes without invoking an LLM or recalculating clinical risk; repeat startups skip users whose baseline already includes their latest observation. Previous canonical baseline rows (`canonical-structural-v1` and `-v2`) are marked `superseded` rather than deleted. Each `BaselineVersion` records the comparison window it left out in `exclusions`, with per-type observation counts, and `GET /api/v1/baselines/current`, `GET /api/v1/state` and the professional reads return that list. Observations from only the last week therefore give `insufficient_data` rather than a self-comparison that reads as `stable`.

Hoy reads `longitudinal` from `GET /api/v1/state` and charts the 30-day series from `GET /api/v1/timeline?window_days=30`. The chart shows observations and does not calculate the change. Tendencias uses those same two reads: the comparison comes from `state.longitudinal`, and the chart from the timeline. It does not call `/api/v1/baselines/current` or `/api/v1/changes`. A calculated band is explained in Spanish. An uncalculated feature is described as a missing comparison, and the page says that a missing calculation is not evidence that things are fine. The raw band code stays off the page. Change stays apart from `safety.alert_level`.

`embed_change_signals` (`backend/app/services/change_signal_embeddings.py`) runs only from `POST /api/v1/analytics/run`, after the trajectory commit. A check-in refresh does not write these rows. The writer returns 0 unless the user is active and `linguistic_analysis` is currently granted. It skips a signal whose feature name contains `crisis`, `chemsex`, `ghb`, `gbl`, `restraint`, `suicid`, `self_harm` or `self-harm`, and it skips a signal that already has a row. The stored vector is 16 floats from SHA-256 of `feature|change_value|band|algorithm_version` (`provider=local_deterministic`, `embedding_model=change-signal-fingerprint-v1`). It does not call an embedding model and it does not read or write `alert_level`.

## Single-patient sequence layer

This layer is not the canonical trajectory above and it is not on the check-in or `/api/v1/state` path. `TimeAwareSequenceModel` (`backend/app/services/sequence_model.py`, `patient-sequence-v1`) is a pure-Python helper used by tests. It does not insert `ChangeSignal` rows and it does not write `RiskAssessment.alert_level`.

Allowed input is app chronology the caller already built: check-ins, diary, chat and confirmed facts. Any event whose `source_refs` include a value starting with `clinical_document:` is dropped before scoring. `clinical_document_analysis` does not make that prefix eligible. Naive timestamps are treated as UTC. Fewer than `min_points` events after that filter (default 3) returns an empty list. If none of the remaining events fall inside `window_days` of now (default 365), the result is also empty. Older events stay in the spacing baseline; they are not scored as the current point.

The model does not read the database and does not filter events by `patient_id`. The caller supplies one patient's events; `patient_id` is copied onto the draft.

One run emits at most one `ChangeSignalDraft`, for the newest in-window event. The score compares that event's age with the mean gap, in days, between strictly earlier events, including events outside the window. `effect = 1 - min(age / mean gap, 1)`, kept only when it is greater than 0: `1` means the newest event is dated now, and an age at least as long as the mean gap produces no draft. No earlier spacing, or fewer than two earlier events, also yields no draft. That `effect` is not a z-score and not a `stable` / `transition` / `unstable` band. `confidence` starts at `0.4 + 0.4 * (count of events that passed the document filter / min_points)`, gains `0.05` when the scored event's remaining `source_refs` contain `check_in`, `diary`, `chat` or `fact`, and is capped at `0.95`. The `source` field is not part of that bump. The explanation string is fixed: `cambio respecto a la línea propia del paciente`.

`backend/app/services/sequence_dlearning.py` is the optional ML proposal (`patient-sequence-dl-v1`). The module enables ML only when `torch`, `tensorflow` and `sklearn` all import. `backend/requirements-ml.txt` lists `torch` and `scikit-learn` and is not part of the API image; it does not list `tensorflow`, so installing that file leaves `requires_ml()` false and the deterministic helper in place. `requires_consent` returns false when ML is unavailable, when `linguistic_analysis` is not granted, or when the consent read fails. It does not raise, and it does not run a training loop. `SEQUENCE_DLEARNING_CONFIG` may point at a JSON file; a missing or unreadable file keeps `DEFAULT_CONFIG`.

`sequence_refs` in `backend/app/services/sequence_sources.py` is the part that does run in product code. It strips `clinical_document:` refs. Memory retrieval uses it when copying list-shaped source refs (`retrieve_longitudinal_context`). The patient-understanding chronology drops professional-document rows and the same prefix before consolidation (`is_external_clinical_doc`).

## Patient export and erasure

Both routes require a signed-in patient.

`GET /api/v1/me/data-export` returns `schema=psychdeep-data-export-v1`: account, consents, check-ins, diary entries, confirmed facts and the safety plan (portability), plus risk assessments and assignment ids (access copy). It does not include chat text, observations, ChangeSignals or memory rows.

`POST /api/v1/me/erasure-request` does not delete those rows. It revokes the offered purposes (`data_processing`, `linguistic_analysis`, `clinical_document_analysis`, `professional_sharing`), writes a `granted=false` consent row for each, ends pending, active and paused assignments, deactivates the account and increments `auth_version`. The response is `status=processing_stopped`, `hard_delete=false`. Audit action: `erasure_request`.

## Curated knowledge

`knowledge_items` is a versioned registry. The professional dashboard has no screen for it. Only `admin_clinical` writes it. `POST /api/v1/knowledge` accepts:

```json
{
  "topic": "respiracion",
  "population": "adultos",
  "objective": "bajar-activacion",
  "locale": "es-ES",
  "evidence_level": "revision-interna",
  "contraindications": ["dolor-toracico"],
  "content": "Texto de al menos veinte caracteres.",
  "content_version": "2026-10-02",
  "review_due": "2027-01-01",
  "source_ref": "protocolo-interno-v3"
}
```

`review_due` must be after today or the draft is rejected. `POST /api/v1/knowledge/{id}/approve` activates a draft and retires every other `active` row with the same topic, population, objective and locale. `POST /api/v1/knowledge/{id}/retire` marks a row `retired`.

`GET /api/v1/knowledge/retrieve` is available to therapist, supervisor and `admin_clinical`. It matches population, objective, topic and locale exactly, drops rows whose contraindications overlap the query, and returns rows only. The handler makes no model call.

Agent 1 reads the table directly. `agent1_context._knowledge_block` loads every `active` row whose `review_due` is null or still today or later, then appends topic, objective, evidence level and the full content. Selection uses status and review date only, so a row can be included even when it lists contraindications or targets another population. A query error yields an empty block. Sections are packed in order under `conversation_context_block_budget_tokens` (default 6500). Knowledge is last. When the budget runs out, that block is shortened or omitted. An earlier section is shortened only when that section is the one that crosses the ceiling.

`ModelRun` stores `input_hash`, `prompt_version` and `policy_version`. Retiring an item changes the next prompt. Past runs can be correlated by input hash, not by `content_version`.

## Patient information architecture

- **Hoy** — low-burden check-in, change versus the personal baseline (separate from the alert level), and a 30-day chart of recorded values.
- **Tendencias** — personal baseline, missingness, and a plain-language reading of change signals. An uncalculated comparison is described as missing data.
- **Regular** — urge-surfing wave, guided breathing, STOP and non-harmful grounding.
- **Diario** — free/structured entries; linguistic analysis requires separate consent.
- **Plan** — editable safety/prevention plan.
- **Compartir** — professional links, consent and consultation preparation.
- **Cuenta** — account/security.

The crisis control remains persistent for patients and does not depend on the LLM.

## Zero-cost prototype deployment

Current prototype keeps the already-provisioned free components:

- Render free `psychdeep-api` and `psychdeep-web`.
- Existing Supabase `psychdeep` project as the only clinical database.
- Local inference through the existing Cloudflare Tunnel when selected.
- Anthropic remains an explicitly selectable approved provider when its server-side key is configured; its usage is not part of the zero-cost guarantee.
- No new paid database, worker, queue or managed GPU is required for this stage.

See [DEPLOY.md](DEPLOY.md) for the deployment sequence and `docs/` for ADRs, runbooks and release gates.

## Frontend UX & Accessibility Quality

When updating or creating forms in the frontend, ensure that inputs have explicitly associated labels utilizing `htmlFor` and unique `id`s. Avoid orphaned inputs. Required inputs should present visual required indicators (e.g., `*` with an `aria-hidden` attribute for screen readers).

## Development and quality gates

```bash
cd backend
python -m pytest tests/ -q

cd ../frontend
npm ci
npm test
npm run build
```

Pull requests also apply and re-apply every Supabase migration against PostgreSQL and execute `supabase/verify.sql`. A release is blocked by failing risk/safety tests, migration loss, authorization negative-test failure, missing audit/provenance, unsafe model fallback, or an unanswered release-checklist item.

## Release checklist

Every release must have verifiable answers to all eight questions:

1. What changes for the user?
2. What new data is used and under what consent?
3. What can go wrong clinically?
4. What does the LLM decide — and what does it **not** decide?
5. Can the relevant decision be reproduced?
6. Is there a negative authorization test?
7. What happens when the model is unavailable?
8. How is the release rolled back?

If any answer is missing or unverifiable, the change is not production-ready.

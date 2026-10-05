# PsychDeep vNext

PsychDeep is a cloud-first longitudinal self-regulation platform. Its purpose is to help a person understand changes relative to their own trajectory, strengthen self-efficacy, use low-intensity regulation tools and collaborate with authorised professionals without turning an LLM into a clinician.

The master product/engineering specification is the release authority. Approved ADRs/change requests may refine its implementation contract when product requirements are clarified.

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
       ├── local-tunnel ──HTTPS──► local OpenAI-compatible LLM (LM Studio/Ollama/etc.)
       ├── cloud-tuned ──────────► approved private managed inference endpoint
       └── Anthropic ────────────► approved commercial provider
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

Two selection stores exist. They are not the same screen.

| Mode | Who writes it | What inference uses |
| --- | --- | --- |
| `LLM_PERSONAL_MODE` off, `LLM_ALLOW_RUNTIME_OVERRIDE=true` | `admin_clinical` via `/api/v1/settings/llm` | The active `llm_endpoint_configs` row, or the deployment default |
| `LLM_PERSONAL_MODE` on | `admin_clinical` via **Mis modelos** (`/api/v1/settings/llm/personal`) | That account's saved connection. See below |

**Mis modelos** is limited to `admin_clinical`. The choices are Local, Anthropic, and Codex / ChatGPT. Local does not ask for a model id: inference uses the single model loaded in LM Studio through the tunnel. Codex and Anthropic copy server model ids and server keys (`OPENAI_*`, `ANTHROPIC_*`). When the newest active clinical-admin row is Codex or Anthropic, patient chat, analysis and the copilot use that row. A local LM Studio row stays on the account that saved the key and is not applied to other accounts. The screen does not write `llm_endpoint_configs`.

There is no primary/fallback provider chain. If the selected provider is unavailable, model-dependent functionality fails safely while data entry, deterministic risk/safety and crisis resources remain available. Model credentials remain server-side secrets. Details and the 403 probe are in [docs/integrations/per-user-model-credentials.md](docs/integrations/per-user-model-credentials.md).

## Data migration

vNext uses expand-and-migrate. Existing `psychdeep_v12` records are never rebuilt or reinterpreted in place. Canonical tables are additive and legacy rows remain readable while endpoints move gradually:

`observations`, `feature_definitions`, `feature_values`, `baseline_versions`, `change_signals`, `inferences`, `model_runs`, `intervention_events`, `knowledge_items`, `fine_tune_runs`, `model_deployments`.

The migration backfills canonical compatibility rows with references to legacy sources; original clinical rows remain untouched.

## Check-in trajectory

`POST /api/v1/checkins` requires the patient role and granted `core_processing` consent. It then:

1. Stores the check-in and commits it.
2. Dual-writes `mood`, `craving`, `sleep_hours` and `self_efficacy` into `observations`. Notes become a `checkin_context` observation. That write commits separately.
3. Recomputes the canonical trajectory (`refresh_trajectory` → `run_canonical_analytics`, algorithm `canonical-structural-v1`).
4. Runs the deterministic risk engine. This step still runs when step 3 fails.

`POST /api/v1/observations` stores an observation and does not recompute the trajectory. `POST /api/v1/analytics/run` recomputes it and does not calculate risk. `GET /api/v1/state` only reads stored rows: `safety` is the latest `RiskAssessment`; `longitudinal` is the current `BaselineVersion` plus the newest `ChangeSignal` for each feature on that baseline. Neither read calls a model.

| Input | Rule |
| --- | --- |
| Baseline window | 21 days |
| Recent window | 7 days |
| Axis eligibility | at least 5 observations |
| Craving | scored as `10 - reported craving` (`craving_inv`) |
| Band | absolute z ≤ 1.2 `stable`; ≤ 1.95 `transition`; otherwise `unstable` |
| Missing recent or baseline values | `band=insufficient_data` and `change_value` null |
| Composite | `structural_composite` is another `ChangeSignal`, not a risk level |

A failed refresh logs the exception type and rolls back the analytics transaction. The check-in and observation dual-write stay, because they were already committed. Previous baseline rows for the same algorithm are marked `superseded` rather than deleted.

Hoy charts the 30-day self-report series and reads `longitudinal` from `GET /api/v1/state` for change versus the personal baseline. Tendencias reads `/api/v1/timeline`, `/api/v1/baselines/current` and `/api/v1/changes`. A calculated band is explained in Spanish. An uncalculated feature is described as a missing comparison, and the page says that a missing calculation is not evidence that things are fine. The raw band code stays off the page.

`GET /api/v1/review/weekly` returns a 7-day timeline plus two separate objects: `safety` (latest `RiskAssessment.alert_level`) and `longitudinal` (persisted baseline and change signals, plus the limit that a missing change signal is not evidence of no risk). It does not recompute analytics or call a model.

Authorised professional summaries keep the same split. `latest_alert_level` and `latest_structural_score` / `latest_confidence_band` come from the risk engine. `latest_structural_score` is check-in similarity stored on the assessment, not a `ChangeSignal` band. `longitudinal` is the canonical baseline and change signals. A missing change stays null / `insufficient_data` and is not rendered as zero or as “sin riesgo”.

`admin_clinical` roster rows are the exception: they list assignment links and set `longitudinal` to null, alert fields to null, and `checkin_count` to 0. That null is “this response has no chart”, not a score.

## Assignment reads

`GET /api/v1/assignments/mine` returns links the caller may see. `group=pending` is `status=pending`. `group=done` is every other status (active, paused, ended, rejected). `patient_id` narrows the list for therapist, supervisor and `admin_clinical`. A patient filter cannot read another person’s links; a therapist still only sees links they own.

`GET /api/v1/assignments/all` is supervisor and `admin_clinical` only. `POST /api/v1/assignments/request` is refused for `admin_clinical` (403): that role manages the roster and does not request a clinical link.

`GET /api/v1/professional/patients` for `admin_clinical` attaches `assignments` and a summary `assignment_status`. Summary priority is pending, then active, paused, ended, rejected. No links yields `none`. Pending wins when a patient has both a waiting request and an older link. The same response omits alerts, structural score and `ChangeSignal`. Therapist and supervisor summaries still include the clinical fields for patients they may read.

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

- **Hoy** — low-burden check-in, current context, change versus the personal baseline, and a 30-day chart of recorded values.
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

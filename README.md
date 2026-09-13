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

## Model selection

`MODEL_DEPLOYMENT_ALIAS` defines the deployment default:

- `local-tunnel`: an OpenAI-compatible model on a trusted machine, exposed only through authenticated HTTPS tunnelling when the cloud API needs it.
- `cloud-tuned`: a private/managed compatible endpoint for a reviewed tuned model.
- `commercial-approved`: approved commercial deployment profile.

Production sets `LLM_ALLOW_RUNTIME_OVERRIDE=true`, allowing only the `admin_clinical` role to explicitly switch between the approved Anthropic provider and the local/OpenAI-compatible endpoint from **Modelos/Ajustes**. Every change is audited and affects new model calls only; it does not change consent, storage, risk rules or historical provenance.

There is no primary/fallback provider chain. If the selected provider is unavailable, model-dependent functionality fails safely while data entry, deterministic risk/safety and crisis resources remain available. Model credentials remain server-side secrets. The admin may edit a compatible endpoint URL, but it is validated before activation and is redacted from non-admin users.

## Data migration

vNext uses expand-and-migrate. Existing `psychdeep_v12` records are never rebuilt or reinterpreted in place. Canonical tables are additive and legacy rows remain readable while endpoints move gradually:

`observations`, `feature_definitions`, `feature_values`, `baseline_versions`, `change_signals`, `inferences`, `model_runs`, `intervention_events`, `knowledge_items`, `fine_tune_runs`, `model_deployments`.

The migration backfills canonical compatibility rows with references to legacy sources; original clinical rows remain untouched.

## Patient information architecture

- **Hoy** — low-burden check-in and current context.
- **Tendencias** — longitudinal view, personal baseline, missingness and change signals.
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

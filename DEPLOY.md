# PsychDeep vNext deployment runbook

This runbook deploys the cloud-first vNext architecture without adding paid infrastructure during the prototype stage.

## Target

| Plane | Prototype deployment | Rule |
|---|---|---|
| Web | Render static `psychdeep-web` | Public HTTPS; no persistent clinical offline store |
| API/domain | Render `psychdeep-api` | FastAPI; deterministic safety independent of LLM |
| Clinical data | existing Supabase `psychdeep`, schema `psychdeep_v12` | only authoritative clinical database |
| Model profile A | existing local OpenAI-compatible server via authenticated HTTPS tunnel | inference only; no local clinical DB/API/frontend |
| Model profile B | Anthropic / optional approved managed compatible endpoint | explicit admin selection only; no automatic fallback |
| CI/CD | GitHub Actions + Render auto-deploy | migrations/tests before merge |

No Render Postgres, paid worker, paid cron, managed GPU or additional Supabase project is required.

## 0. Release gates before touching production

Run/verify the pull-request checks:

1. backend pytest, including deterministic safety and authorization-negative tests;
2. frontend tests, typecheck and Vite build;
3. migration apply + re-apply on clean PostgreSQL;
4. `supabase/verify.sql`;
5. security checks/CodeQL where enabled;
6. the eight-item checklist in `docs/release/CHECKLIST.md`.

Do not merge if any P0 gate is red.

## 1. Supabase — expand first

Project: existing `psychdeep` (`ifwexmoltnybvmrsuwtu`). Do not create a second production database.

Apply the vNext foundation migration before the application release. It is expand-only:

- creates canonical observation/feature/baseline/change/inference/model-run tables;
- adds compatibility columns to historical tables;
- backfills canonical references without changing legacy rows;
- enables + forces RLS and grants only the backend role;
- does not grant the old sync role access to new canonical data.

Before and after migration record row counts for historical tables and verify representative UUIDs/read paths. Any loss or reinterpretation is a rollback blocker.

## 2. Render — existing free services

`render.yaml` remains the declarative source for:

- `psychdeep-api`, free plan, Frankfurt;
- `psychdeep-web`, static/free;
- no Render database.

Required non-secret API environment:

```text
APP_ENV=production
DATABASE_SCHEMA=psychdeep_v12
MODEL_DEPLOYMENT_ALIAS=local-tunnel
MODEL_POLICY_VERSION=support-policy-v1
MODEL_ALLOW_COMMERCIAL=true
LLM_ALLOW_RUNTIME_OVERRIDE=true
```

`MODEL_DEPLOYMENT_ALIAS` defines the default. With runtime override enabled, only the `admin_clinical` role may explicitly select Anthropic or the approved OpenAI-compatible local/tunnel endpoint from Settings. The change is written to the audit trail. No patient or ordinary professional account can redirect inference.

`ANTHROPIC_API_KEY`, `MODEL_LOCAL_API_KEY` and equivalent credentials remain Render/server secrets. The UI never receives the Anthropic key. The local endpoint may reuse the deployment token when the runtime selection row contains no token.

Render auto-deploys `master`; do not manually trigger a duplicate deployment after a merge unless auto-deploy is disabled or a cache-clearing redeploy is specifically required.

## 3. Local model + tunnel

The only supported local process is the inference server and, when needed, its tunnel client.

Requirements:

- LM Studio/Ollama/other OpenAI-compatible server bound locally;
- a named HTTPS tunnel/Access policy or equivalent authenticated outbound tunnel;
- no router port-forwarding;
- no PostgreSQL, Docker API, product frontend or product backend exposed;
- prompt/request logs disabled or minimized where the runtime supports it;
- independent endpoint token plus tunnel access control and rotation.

If the selected local endpoint is offline, the application must **not** switch itself to Anthropic. Core clinical data, consent, deterministic risk and static crisis resources remain available; only model-dependent functions degrade until the endpoint returns or an `admin_clinical` explicitly selects another provider.

## 4. Deploy application

After the database expand migration and green CI:

1. merge the reviewed PR to `master`;
2. allow Render auto-deploy to deploy API and web;
3. monitor both deploys to completion;
4. check `GET /api/v1/health`;
5. authenticate a test user and verify: check-in, diary without linguistic consent, consent grant/revoke, Trends, safety plan, deterministic safety evaluation and model status;
6. sign in as `admin_clinical`, verify the Settings provider switch, test both configured providers, and confirm the audit event;
7. verify a local-model outage does not prevent saving data or displaying crisis resources and does not silently route to Anthropic;
8. inspect logs for schema errors and accidental PHI/secrets.

## 5. Retire the old sync path

Only after the cloud release is healthy:

- keep `sync_replication_access` policies removed;
- keep `psychdeep_sync` privileges retired;
- keep SymmetricDS metadata removed;
- retain `llm_endpoint_configs` only as non-secret audited runtime selection history;
- verify no production code references SymmetricDS/local clinical PostgreSQL.

The removed implementation remains recoverable from branch `past/local-offline-sync-20260913`; it is not a runtime fallback.

## 6. Rollback

### Application rollback

Revert the vNext merge or redeploy the last known-good Render commit. The expand migration is intentionally backward-compatible, so the old application can still read its legacy tables.

### Model rollback

An `admin_clinical` may explicitly select the other approved provider or reset to the deployment default. This must be an intentional, audited action. Never silently fall back across providers.

### Database rollback

The initial vNext database change is additive. Prefer application rollback and leave canonical tables dormant. A destructive database rollback is not required and must not be attempted without verified export/backup and Data + QA + Clinical Safety sign-off.

### Sync-retirement rollback

Do not re-enable bidirectional clinical synchronization as an emergency workaround. If access was retired too early, restore only from an explicitly reviewed migration while production remains cloud-authoritative.

## 7. Post-release evidence

Archive in the PR/release record:

- commit SHA and migration name/version;
- CI results;
- historical and canonical row-count checks;
- Supabase security/performance advisor output;
- Render deploy IDs and health result;
- active model provider/model health result, never its secret;
- audit evidence for a runtime provider switch;
- answers to all eight release-checklist questions;
- rollback commit/migration reference.

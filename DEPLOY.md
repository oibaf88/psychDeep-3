# Deploy PsychDeep 3

This is the single runbook for the **PsychDeep 3 Local · Offline · Tunnel · Sync** architecture. Claude through Anthropic is the connected-service default; Gemma 2 through LM Studio is the autonomous/offline alternative. A green local test does not prove Supabase, Render, Anthropic, Cloudflare Access, or the Gemma 2 tunnel is live.

## Target architecture

| Component | Service | Boundary |
|---|---|---|
| Browser client | Render static site `psychdeep-web` | Public HTTPS; API base is baked at build time |
| API | Render Docker service `psychdeep-api` | No direct laptop/LAN route |
| Cloud data | Supabase PostgreSQL, `psychdeep_v12` | TLS, RLS/FORCE RLS, backend role |
| Local data | Docker PostgreSQL 17 | `127.0.0.1:5433` only |
| Local model | LM Studio, Gemma 2 | Authenticated OpenAI-compatible `…/v1` |
| LLM bridge | Cloudflare named Tunnel + Access | Outbound PC connection; LLM endpoint only |
| Cloud/local alignment | SymmetricDS 3.18 | Opt-in 19-table allowlist; laptop initiated |

[`render.yaml`](render.yaml) is the Render source of truth: repository `oibaf88/psychDeep-3`, branch `master`, Claude as default with a server-only Anthropic secret, Gemma 2 fallback values, and no Render database.

## 0. Preflight

```powershell
git remote -v
git branch --show-current
docker compose --env-file .env.local -f docker-compose.offline.yml config --quiet

Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests -q

Set-Location ..\frontend
npm ci
npm test
npm run build
Set-Location ..
```

Expected authority is `https://github.com/oibaf88/psychDeep-3.git` on `master`. Resolve unrelated local changes before pushing; do not reset or discard a worktree that may contain data-operation work.

## 1. Supabase — expand first, preserve history

Project: `psychdeep` (`ifwexmoltnybvmrsuwtu`). Schema: `psychdeep_v12`.

1. Take a current Supabase backup/snapshot.
2. Review `supabase/migrations/20260909062808_add_user_account_security.sql`. It is one transaction, adds only `users.first_name`, `last_name`, `phone`, `auth_version`, and `updated_at`, and does not delete, rename, rebuild, or reinterpret clinical tables/rows.
3. With an authenticated, linked Supabase CLI, inspect migration state:

   ```powershell
   npx --yes supabase migration list --linked
   ```

4. Apply the pending migration using the approved project migration workflow: Supabase CLI `db push --linked` or the Supabase SQL Editor migration batch. Use an owner-capable migration operator, never the app backend role. Never commit a database password.
5. Run the read-only [`supabase/verify.sql`](supabase/verify.sql). Every row must be `ok`: required columns, ownership, RLS/FORCE RLS, backend policy, no PostgREST read grants, and no application tables in `public`.
6. Run a read-only count/UUID/provenance check against established clinical tables before/after. Do not export clinical text. A failure must roll back as a unit; never hand-edit partial state.

## 2. Cloudflare — publish only LM Studio inference

1. In Cloudflare Zero Trust create a **named** Tunnel. Do not use a disposable quick tunnel.
2. Map a hostname such as `llm.example.org` only to `http://host.docker.internal:1234` on the PC running Docker Desktop and LM Studio.
3. Put Cloudflare Access in front of the hostname and create the necessary machine/service authorization for the Render API boundary.
4. Load Gemma 2 in LM Studio, enable API-token authentication, start the server, and confirm the exact name from `GET /v1/models` (initially `gemma-2-2b-it`).
5. On the PC run:

   ```powershell
   ./ops/local/start-tunnel.ps1
   ```

6. Test the protected public URL from an authorized operator context. It must be HTTPS and end in `/v1`.

Never publish `5432`, `5433`, `31415`, Docker, the local web UI, or an unauthenticated LM Studio server. Rotate any exposed tunnel/LM Studio token.

## 3. Render Blueprint and secret values

In Render: **New → Blueprint**, select `oibaf88/psychDeep-3`, choose the intended workspace, and let Render read [`render.yaml`](render.yaml). Do not create a competing service/database architecture manually.

Set the Render `psychdeep-api` values marked `sync: false`:

| Key | Exact value shape |
|---|---|
| `DATABASE_URL` | Supabase session-pooler SQLAlchemy URI with TLS and `search_path=psychdeep_v12` |
| `ANTHROPIC_API_KEY` | Anthropic API key stored only as a Render secret; required by the default Claude route |
| `LLM_OPENAI_COMPATIBLE_BASE_URL` | `https://<protected-cloudflare-host>/v1` |
| `LLM_OPENAI_COMPATIBLE_API_KEY` | LM Studio API token; supply Access authorization at the proxy boundary when required |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` | Optional; only for outbound alert email |

The tracked blueprint sets:

```dotenv
LLM_DEFAULT_PROVIDER=anthropic
ANTHROPIC_CHAT_MODEL=claude-opus-5
ANTHROPIC_ANALYSIS_MODEL=claude-opus-5
LLM_OPENAI_COMPATIBLE_CHAT_MODEL=gemma-2-2b-it
LLM_OPENAI_COMPATIBLE_ANALYSIS_MODEL=gemma-2-2b-it
LLM_OPENAI_COMPATIBLE_COPILOT_MODEL=gemma-2-2b-it
LLM_ALLOW_RUNTIME_OVERRIDE=false
SEED_DEMO_DATA=false
```

For `psychdeep-web`, set `VITE_API_BASE_URL` to the public `psychdeep-api` URL, for example `https://psychdeep-api.onrender.com`. Vite compiles that value into the static bundle, so redeploy `psychdeep-web` after changing it. Set API `CORS_ORIGINS` to the exact static-site/custom-domain origins; never use a wildcard in production.

Render generates `JWT_SECRET`. Do not seed demo accounts in a public/cloud environment.

## 4. Release sequence

1. Supabase backup, migration, and verification complete.
2. `ANTHROPIC_API_KEY` is configured as a Render secret for the default Claude route; if Gemma 2 is selected, its Cloudflare Tunnel endpoint is authenticated and reachable from the cloud boundary.
3. Render secrets, CORS, and static API base are configured.
4. Deploy `psychdeep-api` and wait for a healthy release.
5. Deploy/redeploy `psychdeep-web`.
6. Exercise the hosted flow only with non-clinical test accounts first.

Health endpoint:

```text
https://<psychdeep-api>/api/v1/health
```

It proves API health/configuration, not successful model inference. Use the authorized administrator endpoint test and inspect sanitized Render logs to test the protected LLM route.

## 5. Post-release acceptance

- [ ] Public `/api/v1/health` succeeds.
- [ ] Static web points at the API without CORS errors.
- [ ] Claude/Anthropic is effective by default and its key is a Render secret; if Gemma 2 is selected, its endpoint is protected HTTPS and not a LAN/loopback address from Render.
- [ ] Deterministic risk remains available when the model/tunnel fails; no LLM controls alert levels.
- [ ] Patient, therapist, supervisor, and clinical admin receive only authorized data/routes.
- [ ] **Mi cuenta** works for every profile; password change requires fresh login.
- [ ] Selected-user permissions view/print excludes clinical data; revoke blocks existing tokens; restore requires new login.
- [ ] Existing clinical history, risk traces, timelines, and historic model provenance remain readable.
- [ ] `supabase/verify.sql` remains all `ok`.
- [ ] Logs contain no clinical prompt, secret, tunnel token, or raw provider error body.

## 6. Enable sync only after cloud acceptance

Synchronization does not start on Render or in `start-local.ps1`. On the local PC, after backup, explicit operator review, and a disposable non-clinical test:

```powershell
./ops/sync/configure-sync.ps1
./ops/sync/start-sync.ps1 -Initialize
```

The configuration stores the `psychdeep_sync` credential under Git-ignored `ops/local/secrets/`. Initialization performs the cloud preflight, creates SymmetricDS metadata in `psychdeep_sync`, installs the fixed 19-table allowlist, opens a narrowly scoped registration, and starts the local node.

Check `127.0.0.1:31415`, container logs, queued batches, and cloud/local audit markers. Do not use a clinical record to test. If concurrent mutable account/admin changes conflict, retain audit facts, resolve to the latest authorized update under clinical governance, and record the resolution—never silently discard a clinical decision.

## 7. Incident posture

- **Model/tunnel failure:** stop/disable the tunnel; deterministic features remain safe. Never point Render to `localhost` or a private LAN IP.
- **Render failure after migration:** retain the prior healthy service while investigating. Do not roll back additive fields that a new release may already use; forward-fix after backup.
- **Sync issue:** stop only the `symmetricds` profile, retain the local Docker volume and cloud DB, inspect batches/audit state, then resolve. Never run `down -v`.
- **Secret exposure:** rotate the relevant Cloudflare, LM Studio, Supabase, SMTP, or Render credential and redeploy.

## Change control

`psychDeep-3`/`master` is authoritative. Schema/security changes are reviewed and deployed explicitly, then evidenced in the live environment. The local stack is a real autonomous copy—not a browser mockup of the Render service.

# PsychDeep 3

PsychDeep 3 is the reference implementation of the supplied **Local · Offline · Tunnel · Sync** architecture. It is a responsive web application: one local browser client, a local PostgreSQL copy, and the same API used by the hosted service. The historical nested repository, native Windows wrapper, mobile/PWA package, mobile telemetry path, alternate local-ML program, and old Compose entry point have been removed.

> PsychDeep supports self-regulation and clinical workflow. It is not a medical device. Neither Claude nor Gemma 2 determines a clinical risk level; the risk engine is deterministic and auditable.

## Reference architecture

```text
                         HTTPS + authenticated LLM route only
Render API ──────────────────────────────────────────────────────────┐
                                                                     ▼
Render static web ───────► Supabase PostgreSQL       Claude / Anthropic API (default)
                               psychdeep_v12                    outbound only
                                      ▲                                  ▲
                                      │  SymmetricDS 3.18 (two-way)       │
                                      │  opt-in; laptop initiates         │
                                      │                                  │
Browser ◄── 127.0.0.1:5173 ◄── local frontend ◄── local backend ◄── local PostgreSQL 17
                                      Docker Compose                     127.0.0.1:5433
```

Claude through Anthropic is the connected-service default and its `ANTHROPIC_API_KEY` is an environment secret only. The local stack intentionally overrides that selection to Gemma 2 so browser, API, local PostgreSQL, deterministic processing, replicated history, and inference can keep working offline on the PC. If enabled, SymmetricDS queues offline local changes and copies only the fixed allowlist when online. The cloud never opens an inbound PostgreSQL connection to the laptop.

Cloudflare Tunnel is **only** for the local LM Studio OpenAI-compatible endpoint so that Render can reach it over HTTPS. It must never carry PostgreSQL, Docker, the local browser, or administration ports.

## Historical clinical data remains compatible

- The app retains established `psychdeep_v12` tables, UUIDs, relationships, audit records, deterministic risk traces, model provenance, and historic provider labels.
- `20260909062808_add_user_account_security.sql` is expand-only: it adds account data and session-version fields to `users`; it does not rebuild, rename, backfill, delete, or reinterpret clinical tables/rows.
- Password, role, revocation, and restore changes only bump `users.auth_version` so old JWTs become invalid. Clinical content is never touched.
- Sync has a fixed 19-table allowlist in `ops/sync/config/psychdeep-sync.sql`. Reset tokens, endpoint secrets/configuration, and SymmetricDS internal tables are excluded.

Do not use a clinical record to test synchronization. Take a backup and test initial sync using a disposable, non-clinical account/row.

## Authoritative entry points

| Purpose | Location / command |
|---|---|
| Local/offline service definition | `docker-compose.offline.yml` |
| Start local browser/API/database | `./ops/local/start-local.ps1` |
| Stop without deleting the local DB | `./ops/local/stop-local.ps1` |
| Optional LLM tunnel | `./ops/local/start-tunnel.ps1` |
| Generate sync engine settings | `./ops/sync/configure-sync.ps1` |
| Start or initialize sync | `./ops/sync/start-sync.ps1 [-Initialize]` |
| Cloud infrastructure | `render.yaml` |
| Production migrations | `supabase/migrations/` |
| Read-only production verification | `supabase/verify.sql` |
| Cloud runbook | [DEPLOY.md](DEPLOY.md) |

There is intentionally no `docker-compose.yml`, `start.ps1`, `START.bat`, phone launcher, native wrapper, or PWA installer.

## Start the autonomous local copy

### Requirements

- Docker Desktop with its engine running.
- LM Studio with **Gemma 2** loaded; initial model ID: `gemma-2-2b-it`. Always use the exact ID reported by LM Studio at `/v1/models`.
- PowerShell from this repository root.

### Local secrets and settings

```powershell
Copy-Item .env.local.example .env.local
python -c "import secrets; print(secrets.token_hex(32))"
```

Put the generated value into `JWT_SECRET` in `.env.local`, and set a unique `LOCAL_DB_PASSWORD`. Both remain Git-ignored. Keep these PDF-architecture values unless LM Studio reports a different model identifier:

```dotenv
LLM_DEFAULT_PROVIDER=openai_compatible  # local/offline override; product default is anthropic
LLM_OPENAI_COMPATIBLE_BASE_URL=http://host.docker.internal:1234/v1
LLM_OPENAI_COMPATIBLE_API_KEY=<LM Studio API token>
LLM_OPENAI_COMPATIBLE_CHAT_MODEL=gemma-2-2b-it
LLM_OPENAI_COMPATIBLE_ANALYSIS_MODEL=gemma-2-2b-it
LLM_OPENAI_COMPATIBLE_TIMEOUT_SECONDS=300
```

In LM Studio: load Gemma 2, start the server on port `1234`, enable **Require Authentication**, make an API token, and allow Docker to reach it through `host.docker.internal`. Do not publish LM Studio to the public Internet.

### Run and stop

```powershell
./ops/local/start-local.ps1
```

- App: <http://127.0.0.1:5173>
- API health: <http://127.0.0.1:8001/api/v1/health>
- API docs: <http://127.0.0.1:8001/docs>
- Database: `127.0.0.1:5433`, local machine only

```powershell
./ops/local/stop-local.ps1
```

This preserves the `psychdeep_offline_db` Docker volume. **Never add `-v`** unless intentionally deleting the database after a verified backup.

## Account, permission, and visual features

All authenticated roles have **Mi cuenta**: name, surname, email, phone, locale, and password can be changed. Email change requires the current password. Passwords require at least 12 characters and reject bcrypt's unsafe truncation beyond 72 UTF-8 bytes. Rotating a password invalidates all sessions.

Clinical administration uses a selected-user-only view:

- list selection displays that account's effective permissions and access state, not its clinical record;
- **Imprimir / guardar PDF** calls the browser print dialog for a permissions-only document, and the server stores no sensitive PDF;
- role change, revoke, restore, view, and print requests are audited;
- revocation invalidates existing JWTs; self-revocation and removal/demotion of the final active clinical admin are blocked.

The **Wave** uses layered water movement, becoming a storm at high intensity. The logo-derived breathing mark opens as a large temporary foreground exercise, dismissible by **Volver**, `Esc`, or click outside. `prefers-reduced-motion` disables the moving effects.

## Sync (operator-controlled, two-way)

`start-local.ps1` never starts synchronization automatically. Follow this sequence only after the cloud release has passed acceptance:

1. Confirm Supabase migrations and the least-privilege `psychdeep_sync` operator role from [DEPLOY.md](DEPLOY.md).
2. Back up the cloud database and preserve the local Docker volume.
3. Obtain the `psychdeep_sync` password through a secure operator handoff. Never commit it or put it on a command line.
4. Generate local engine files:

   ```powershell
   ./ops/sync/configure-sync.ps1
   ```

5. Review the 19-table allowlist and validate a disposable non-clinical record.
6. Initialize exactly once:

   ```powershell
   ./ops/sync/start-sync.ps1 -Initialize
   ```

7. For routine restarts:

   ```powershell
   ./ops/sync/start-sync.ps1
   ```

Clinical events are history-oriented and normally replicate as traceable inserts. If a mutable shared account/administrative row is changed at both ends before synchronization, do not silently discard a clinical decision: inspect audit timestamps, select the latest authorized update, and record the resolution.

## Cloudflare Tunnel for local Gemma 2

Create a named Cloudflare Tunnel and Access-protected hostname before running the local script. Map **only** that hostname to `http://host.docker.internal:1234`; keep LM Studio API-token authentication enabled.

```powershell
./ops/local/start-tunnel.ps1
```

The tunnel token stays in Git-ignored `ops/local/secrets/cloudflare-tunnel-token.txt`. In Render, set the final HTTPS `/v1` URL and LM Studio token as `LLM_OPENAI_COMPATIBLE_BASE_URL` and `LLM_OPENAI_COMPATIBLE_API_KEY`. See [DEPLOY.md](DEPLOY.md) for Access and Render sequencing.

## Validate changes

```powershell
# Backend — run inside backend so the new app package is selected
Set-Location backend
.\.venv\Scripts\python.exe -m pytest tests -q

# Frontend
Set-Location ..\frontend
npm ci
npm test
npm run build

# Compose syntax only
Set-Location ..
docker compose --env-file .env.local -f docker-compose.offline.yml config --quiet
```

`supabase/verify.sql` is read-only. Use it before and after a release; local tests do not prove a hosted release, protected tunnel, or cloud database path is live.

## Security invariants

- Secrets and generated sync/tunnel files are Git-ignored; none go in tracked files.
- Local frontend, API, and database bind to loopback only.
- Supabase uses `psychdeep_v12`, TLS, RLS/FORCE RLS, and least-privilege backend/sync roles from migrations.
- Cloud model endpoints must be public HTTPS; private/LAN endpoints are rejected from Render. Cloudflare never exposes database ports.
- Password rotations, role changes, revocations, and restores invalidate JWTs.
- Historic provenance remains readable, while the connected default is Claude/Anthropic and the autonomous local alternative is Gemma 2.

The authoritative remote is `oibaf88/psychDeep-3` on `master`. Apply schema changes explicitly and preserve local worktree/database state rather than forcing it to match a remote revision.

# PsychDeep: inference connection for the clinical admin

## Security contract

The operator configures **one Cloudflare Access Service Token** (Client ID and Client Secret) in the Render **backend** `psychdeep-api`, never in the React frontend. The `cloudflared` **connector** token belongs only to the Windows `cloudflared` service and is not an HTTP authentication credential. Cloudflare Access protects `ai.bfab.io`; its policy must allow the exact Service Token used by Render.

Only `admin_clinical` opens **Mis modelos** (`/settings`) and calls `GET`, `PUT`, `DELETE` and `POST /test` on `/api/v1/settings/llm/personal`. Patient, therapist and supervisor accounts cannot read or change that connection. The screen offers three providers:

| Screen label | Stored row | Credentials |
| --- | --- | --- |
| Local | `provider=openai_compatible`, `base_url` empty | That admin account's LM Studio bearer, plus the operator Access pair |
| Codex / ChatGPT | `provider=openai_compatible`, `base_url=https://api.openai.com/v1` | `OPENAI_API_KEY` and `OPENAI_CHAT_MODEL` / `OPENAI_ANALYSIS_MODEL` / `OPENAI_COPILOT_MODEL` |
| Anthropic | `provider=anthropic` | `ANTHROPIC_API_KEY` and the `ANTHROPIC_*_MODEL` settings, and only when `MODEL_ALLOW_COMMERCIAL` is on |

The personal API rejects extra fields, including an endpoint URL. **Mis modelos** sends empty model ids. Codex and Anthropic then copy the server model ids. Local ignores the request ids and reads the loaded LM Studio model.

An LM Studio token is encrypted with the stable Fernet `LLM_USER_CREDENTIALS_KEY` held only in Render and stored on that account's `llm_user_preferences` row. GET returns `lm_api_key_configured`, never the token. On PUT, null preserves the ciphertext, an empty string revokes it, and a nonempty value rotates it. DELETE removes only that account's row. The browser clears the key field after a successful save. Nothing is written to `localStorage` or a frontend build variable.

When the saved provider is local, the backend calls the pinned `https://ai.bfab.io/v1` endpoint with `CF-Access-Client-Id` and `CF-Access-Client-Secret` from Render, plus `Authorization: Bearer <that account's decrypted LM Studio token>`. A missing or undecipherable token, incomplete Access setup, or a target that is not the approved HTTPS `/v1` host **fails closed**. It does not reuse `MODEL_LOCAL_API_KEY` or another account's token, and it does not fall back to Anthropic or OpenAI.

## Which connection a request uses

`LLM_PERSONAL_MODE=true` makes `get_llm_provider` call `personal_llm.resolve_active`. That function looks up the latest `llm_user_preferences` row owned by an active `admin_clinical` user (`updated_at` descending).

- If that row is Codex or Anthropic, chat, analysis and the professional copilot for every account use it. Patient chat does not keep calling the tunnel after that save.
- If that row is local, it stays on the account that stored the LM Studio key. Other accounts resolve their own row. A patient with no row cannot inherit the admin key.
- If several clinical admins have rows, only the newest row is considered. An older Codex row does not apply while a newer local row is the latest.

`LLM_PERSONAL_MODE` unset or false keeps the deployment default and, when `LLM_ALLOW_RUNTIME_OVERRIDE=true`, the audited `llm_endpoint_configs` row from `/api/v1/settings/llm`. **Mis modelos does not write that table.** The current Settings screen calls only `/api/v1/settings/llm/personal`.

## Local model id

Local inference reads the catalog LM Studio is serving (`/api/v0/models`, then `/v1/models`) through the tunnel. `select_model` is called with an empty requested id:

- one model marked loaded → that id;
- otherwise exactly one advertised id → that id;
- several advertised ids and not exactly one loaded → no id, and inference raises `LocalModelUnavailable` instead of guessing;
- catalog unreachable and no requested id → no id.

Leave `MODEL_LOCAL_CHAT_MODEL`, `MODEL_LOCAL_ANALYSIS_MODEL` and `MODEL_LOCAL_COPILOT_MODEL` empty. A pinned name such as `gemma-2-2b-it` is not a menu choice on this screen.

## One-time operator setup

1. Windows: keep tunnel `workflare` online; Cloudflare public hostname `ai.bfab.io` targets `http://localhost:1234`. Keep LM Studio bound to loopback and **Require Authentication** enabled. Issue an LM Studio API token to the clinical admin; do not expose port 1234 publicly.
2. Cloudflare Zero Trust: create a self-hosted Access application for `ai.bfab.io` and a **Service Auth** policy specifically including the Service Token provisioned for the backend. An Access token that exists but is not included in the policy returns 401/403. Do not bypass Access or disable LM Studio authentication to address errors.
3. Render `psychdeep-api` → Environment: configure `MODEL_LOCAL_BASE_URL=https://ai.bfab.io/v1`, `MODEL_LOCAL_CF_ACCESS_HOST=ai.bfab.io`, `MODEL_LOCAL_CF_ACCESS_REQUIRED=true`, `MODEL_LOCAL_CF_ACCESS_CLIENT_ID` and `MODEL_LOCAL_CF_ACCESS_CLIENT_SECRET`. Leave the three `MODEL_LOCAL_*_MODEL` variables empty. Set `OPENAI_API_KEY` before Codex can be saved, and `ANTHROPIC_API_KEY` plus `MODEL_ALLOW_COMMERCIAL=true` before Anthropic can be saved.
4. **Preserve** the existing `LLM_USER_CREDENTIALS_KEY` Fernet key. Never replace it without a migration that decrypts and re-encrypts all existing ciphertext. No separate Supabase migration is required beyond `psychdeep_v12.llm_user_preferences` (backend-owned and FORCE RLS). Per-account Access ciphertext columns are legacy and are cleared on the next save.
5. `MODEL_LOCAL_API_KEY` remains only for the non-personal local path in `build_provider`. Do not treat it as the key **Mis modelos** sends. `sync: false` in `render.yaml` does not prompt for new secrets or remove existing values.
6. Before enabling `LLM_PERSONAL_MODE=true`, deploy frontend and backend together. As `admin_clinical`, save Codex and confirm a patient chat uses the server OpenAI key. Save Local and confirm a patient with no stored row does not receive the admin LM Studio token. Probe with synthetic content. Check chat, analysis and copilot, and confirm a down tunnel does not switch provider. Deterministic safety stays available either way. Leave the flag false only for an explicitly reviewed return to `llm_endpoint_configs`.

## Using the screen

Sign in as `admin_clinical`. **Mis modelos** is not in the nav for any other role. Choose Local, Anthropic, or Codex / ChatGPT, then **Guardar conexión** and **Probar conexión**. For Local, paste that account's LM Studio API key. A saved key shows as configured; a blank field keeps it; **Revocar mi API key al guardar** deletes it. The clinical admin does not type the tunnel hostname, Cloudflare credentials, or the `cloudflared` token.

## Diagnosing a 403 safely

A 403 from the synthetic probe can originate at Cloudflare Access **or** LM Studio: the code does not assume one is responsible. First verify that the Access app's Service Auth policy includes the correct Service Token and that the Access ID/secret in Render match it. Independently verify the LM Studio token against `http://localhost:1234/v1/models` and that a model is loaded. Run an HTTP probe **from the backend path** with synthetic content, checking only response status and safe request IDs. Never log headers, token values, clinical prompts, or raw error bodies. A browser access token or a Bypass policy is not a workaround.

Clinical text still passes through the Render backend and Cloudflare on its way to the Windows machine. Local model weights do not make this application offline. An LM Studio key does not grant a PsychDeep account, a patient role, or chart access.

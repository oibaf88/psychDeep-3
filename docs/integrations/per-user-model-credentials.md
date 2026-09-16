# PsychDeep: shared, operator-managed local LLM gateway

## Contract

The clinical administrator/operator provisions the shared gateway ONCE in **Render `psychdeep-api` → Environment**. Every authenticated PsychDeep role can then use the local model with **zero secret entry**. Each account can independently select local inference or Anthropic if explicitly permitted. The exact local model IDs are controlled by the operator in Render so obsolete account preferences cannot accidentally target an unloaded model. New accounts default to local inference when `LLM_PERSONAL_MODE=true`; failures never trigger a silent Anthropic fallback.

The Windows `cloudflared` connector token/secret is **not** an HTTP credential and remains on Windows. Render stores a separate **Cloudflare Access Service Token** (Client ID + Client Secret) and one LM Studio API token. Never place these secrets in `VITE_*` frontend variables, GitHub, Supabase, or user settings. Every local inference request sends both Cloudflare Access headers and the LM Studio Authorization bearer header from the backend.

## One-time setup for the clinical administrator/operator

1. On Windows, keep tunnel `workflare` online. Publish hostname `ai.bfab.io` to `http://localhost:1234`. Run LM Studio's server bound to loopback, with **Require Authentication** enabled, and create one dedicated inference API token. Do not expose TCP port 1234 via LAN or your router.
2. Create a Cloudflare Access **Self-hosted** application protecting `ai.bfab.io` with a **Service Auth** policy that permits only a dedicated PsychDeep backend Service Token and rejects unauthenticated requests. Copy its **Client ID** and **Client Secret**, not the `cloudflared` token.
3. In Render → `psychdeep-api` → Environment (never `psychdeep-web`), set:

   | Variable | Value |
   | --- | --- |
   | `MODEL_LOCAL_BASE_URL` | `https://ai.bfab.io/v1` |
   | `MODEL_LOCAL_CF_ACCESS_HOST` | `ai.bfab.io` |
   | `MODEL_LOCAL_CF_ACCESS_REQUIRED` | `true` |
   | `MODEL_LOCAL_CF_ACCESS_CLIENT_ID` | Dedicated Access Service Token Client ID |
   | `MODEL_LOCAL_CF_ACCESS_CLIENT_SECRET` | Dedicated Access Service Token Client Secret |
   | `MODEL_LOCAL_API_KEY` | One LM Studio inference API token |
   | `MODEL_LOCAL_CHAT_MODEL` | Exact model ID from LM Studio `/v1/models` |
   | `MODEL_LOCAL_ANALYSIS_MODEL` | Exact model ID from LM Studio `/v1/models` |
   | `MODEL_LOCAL_COPILOT_MODEL` | Optional exact model ID, otherwise conversation model |

   Preserve `LLM_USER_CREDENTIALS_KEY`: old per-account ciphertext exists and should remain recoverable during staged rollback. It is never used for inference under the new design. `sync: false` Blueprint entries are **not re-prompted** on updates; set secrets in Render Dashboard yourself.
4. Test that anonymous HTTP requests to `https://ai.bfab.io/v1/models` are denied and that requests with BOTH valid Access headers and the LM Studio bearer work. Use synthetic data only; never paste credentials or full headers into chat, screenshots, GitHub or logs. Verify `cloudflared` and LM Studio stay running.
5. Check Supabase `psychdeep_v12.llm_user_preferences` exists with backend-only RLS. This redesign needs **no new database schema**. Old per-user ciphertext columns remain until rollback is retired; preference updates clear the obsolete ciphertext only for that account. Never bulk-delete old credentials before recovery planning.
6. Merge and deploy frontend/backend only after CI and a security review. Test two accounts (local and Anthropic selections), a newly registered account with no preferences, revoked tokens, misconfigured host, and disconnected Windows server. Confirm that unauthorized users cannot access someone else's data or choose a different upstream destination.
7. Set `LLM_PERSONAL_MODE=true` in Render only after verifying the live gateway and policy. Monitor usage, concurrency and rate limits: a shared LM Studio key identifies the app, not individual users, so authentication and per-account authorization remain in PsychDeep.

## Simplified end-user interface

Users log in and open **Mis modelos**. Local inference is the default; they enter no key, Access credential, URL or model ID. The screen displays read-only local model names provisioned by the administrator. Users may switch to Anthropic if permitted; its approved API key remains on the server. Personal Anthropic API keys and per-account spending limits are **not** implemented by this change.

## Security and rollback

- Backend pins the operator-approved HTTPS `/v1` hostname. The preference API rejects unknown fields, including credentials and arbitrary URLs. Both independent HTTP authentication layers are required for local inference; secrets are not sent to browsers or returned by preferences/status endpoints.
- Shared-key provisioning reduces complexity but increases the impact of compromise. Revoke both shared server tokens if compromised, restrict signup/account permissions, monitor usage and enforce quotas or rate limiting before exposing service to untrusted users. An LM Studio key alone never grants access to clinical records.
- Prompts still travel via Render and Cloudflare to your Windows machine. Local weights do not make this an offline app and do not remove clinical-data compliance requirements.
- If the gateway fails after cutover, model-dependent functions must fail safely without switching automatically to Anthropic; retain independent deterministic safety functions. `LLM_PERSONAL_MODE=false` intentionally restores the older global provider path and requires separate review before rollback.

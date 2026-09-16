# PsychDeep: shared, operator-managed local LLM gateway

## Contract

A clinical administrator/operator provisions the shared gateway ONCE in **Render `psychdeep-api` → Environment**. Patients, therapists, supervisors and administrators then sign in to PsychDeep and can use the local model with **zero API keys in their browser**. Each account may independently select LM Studio or Anthropic when Anthropic is enabled; that selection never changes anyone else's provider. New accounts default to the shared local model when `LLM_PERSONAL_MODE=true`. If it is unavailable, the application fails closed rather than silently sending clinical text to Anthropic.

The Windows `cloudflared` tunnel connector token/secret is **never** an HTTP credential; keep it on Windows. The secret to store in Render is a **Cloudflare Access Service Token**, which consists of Client ID and Client Secret. Render also stores one LM Studio API token. Never put those values in a frontend `VITE_*` variable, the repository, Supabase, or a user's account settings. Every model request uses both Cloudflare Access HTTP headers and the LM Studio Authorization bearer header. Cloudflare Access protects the published hostname, and LM Studio independently requires its token.

## One-time operator setup

1. On Windows, keep tunnel `workflare` connected; its Cloudflare published application must route `ai.bfab.io` to `http://localhost:1234`. Start LM Studio's server on localhost port 1234. Do not enable LAN listening or open the router port. Enable **Require Authentication** in LM Studio and create a dedicated, inference-only API token. Disable LM Studio MCP capabilities that are not required.
2. Create a Cloudflare Access **Self-hosted** application covering `ai.bfab.io`, require a **Service Auth** policy allowing only one dedicated PsychDeep-backend Service Token, and deny unauthenticated access. Generate and securely copy that Service Token's Client ID and Client Secret. Do not copy the `cloudflared` connector token.
3. In Render's backend service `psychdeep-api` (NEVER the static site `psychdeep-web`), configure these values as service environment variables:

   | Variable | Value |
   | --- | --- |
   | `MODEL_LOCAL_BASE_URL` | `https://ai.bfab.io/v1` |
   | `MODEL_LOCAL_CF_ACCESS_HOST` | `ai.bfab.io` |
   | `MODEL_LOCAL_CF_ACCESS_REQUIRED` | `true` |
   | `MODEL_LOCAL_CF_ACCESS_CLIENT_ID` | Dedicated Cloudflare Access Service Token Client ID |
   | `MODEL_LOCAL_CF_ACCESS_CLIENT_SECRET` | Dedicated Cloudflare Access Service Token Client Secret |
   | `MODEL_LOCAL_API_KEY` | Dedicated LM Studio inference API token |
   | `MODEL_LOCAL_CHAT_MODEL` | Exact ID reported by LM Studio `/v1/models` |
   | `MODEL_LOCAL_ANALYSIS_MODEL` | Exact ID reported by LM Studio `/v1/models` |

   Keep the existing `LLM_USER_CREDENTIALS_KEY` untouched: there may be encrypted legacy per-account secrets requiring a controlled deletion/rollback strategy. These legacy credentials are not used by the new resolver. `sync: false` entries in `render.yaml` are **not automatically populated when updating an existing Blueprint**; enter the real secrets in the Render dashboard.

4. Verify a request to `https://ai.bfab.io/v1/models` **without** Access headers is rejected; confirm a request with the correct Access headers and LM Studio bearer returns the available models. Never include the headers, keys or full command in screenshots or chat. The `cloudflared` Windows service needs to be online.
5. Ensure Supabase already has `psychdeep_v12.llm_user_preferences` and its backend-only RLS policy. **No new schema or grant is required** for the shared-credentials design; preferences remain per user, but no new per-user secrets are written. Existing encrypted legacy columns remain mapped only for a controlled rollout; updating a preference deletes that user's old ciphertext. Remove remaining legacy ciphertext only after confirming rollback is no longer required.
6. Merge and deploy frontend and backend together after CI. Validate synthetic requests with two independent test accounts, different provider selections, and one account without saved preferences. Confirm missing Access client ID/secret, missing LM token, incorrect hostname and disabled Access-required mode all fail closed, and that the real service-auth policy rejects anonymous callers.
7. Set `LLM_PERSONAL_MODE=true` in Render **only after** the tests and Cloudflare policy are verified. This activates per-account routing; new users need no model configuration, while saved Anthropic choices remain individual. Monitor performance, concurrency and usage; a shared LM Studio token does not distinguish users at LM Studio itself, so PsychDeep's authentication, audit trail and rate controls remain the authorization boundary.

## User experience

After logging in, open **Mis modelos**. The shared local model is the default, with no secret or URL fields. Optional settings are provider choice and model IDs. When Anthropic is permitted, selecting it uses the already-approved shared Anthropic backend key; personal Anthropic keys and per-user commercial spending limits are not provided by this change.

## Security and rollback

- The backend enforces its configured, pinned HTTPS `/v1` hostname; the browser cannot submit an arbitrary upstream URL or any credential field. Both HTTP authentication layers are required for the personal local provider. No secrets are returned through the preferences endpoint, audits or logs.
- Keeping one gateway credential reduces provisioning but increases shared-key blast radius: revoke/rotate both server tokens on compromise, restrict PsychDeep sign-ups/roles, monitor usage, and apply quotas/rate limits before untrusted public access. A user's app session, not possession of a model API token, authorizes access to clinical data.
- This architecture still routes clinical prompts via Render and Cloudflare to your Windows PC. Local model weights do not make the product offline or exempt it from clinical data handling requirements. Use synthetic data for release verification.
- If readiness fails after cutover, leave model-dependent functions disabled and preserve deterministic crisis/safety features. Do not silently fall back to commercial inference. Rollback to `LLM_PERSONAL_MODE=false` explicitly reactivates legacy global routing, so assess that separately before doing so.

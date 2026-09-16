# Per-user model configuration: deployment and security runbook

This design supersedes the global provider switch in PsychDeep. Every role (patient, therapist, supervisor, admin_clinical) may choose Anthropic or a personal LM Studio configuration. **Cloudflare's cloudflared connector token/secret is not an HTTP credential: it stays on the Windows host and must never be pasted into PsychDeep.**

## Identity, routing and trust boundaries

* The authenticated user's verified database-session identity selects exactly one `llm_user_preferences` row. Request-time inference must not use the process-wide `llm_config` cache; clinical history or patient IDs are not proof of the invoking account.
* For local inference the backend sends THREE credential values in a single HTTPS request: `CF-Access-Client-Id` and `CF-Access-Client-Secret` to Cloudflare Access, and `Authorization: Bearer <user's LM Studio key>` to LM Studio. Neither the browser nor GitHub makes direct requests to `ai.bfab.io`.
* The only permitted target for Access credentials is `https://ai.bfab.io/v1`, pinned by `MODEL_LOCAL_CF_ACCESS_HOST`. The backend rejects plaintext HTTP, other hostnames, userinfo, ports other than 443, paths, queries, and redirects (httpx defaults to no redirects). This prevents an account from redirecting its secrets to an arbitrary host.
* The private keys are encrypted server-side using a stable Fernet key held only by the backend. The database stores ciphertext. GET returns only presence flags and non-secret settings; a blank entry on PUT retains existing ciphertext, `""` revokes it, a nonempty entry rotates it. DELETE removes only the caller's row. Audit logs record only identity, action and provider.
* Anthropic selection is individual but the Anthropic credential remains a **shared backend deployment key**, usable only if `MODEL_ALLOW_COMMERCIAL=true`. Usage/cost limits by account must be considered before opening this to a broad user population; no personal Anthropic key or quota is implemented by this PR.
* When `LLM_PERSONAL_MODE=true`, an account without completed configuration gets a controlled LLM failure, not another person's credentials and not an automatic Anthropic fallback. The deterministic safety engine and static crisis content remain independent of the LLM.

## Stage 1 — Cloudflare + Windows, before merging

1. Ensure the `workflare` Windows service is online. Route the *published application hostname* `ai.bfab.io` to `http://localhost:1234` (HTTP only between cloudflared and loopback); never open port 1234 on the router or LAN.
2. In Cloudflare Access create a **Self-hosted** application covering `ai.bfab.io`, with a Service Auth policy allowing only provisioned service tokens. Test that a request without valid Access headers is denied. A tunnel by itself is not an authorization mechanism.
3. Create and independently distribute a service token per account in Cloudflare Access. Each user enters their own Access Client ID and Client Secret in PsychDeep. Revoking one token must not revoke others. Restrict token permissions and lifetime as the Cloudflare plan permits.
4. Enable API-token authentication in LM Studio and issue separate tokens to the intended accounts (subject to LM Studio's current token management capabilities). Verify that unauthenticated requests, or requests with another/expired key, are denied. No assumption that an LM Studio token authorizes different datasets; patient access controls remain enforced by PsychDeep.
5. Perform tests with synthetic prompts only. Cloudflare and Render still transport/process request metadata and Render transmits the selected text to your home machine; local weights do not imply an offline application or no external infrastructure.

## Stage 2 — database and backend secret

1. Apply and verify `supabase/migrations/20260916150000_add_per_user_llm_preferences.sql`. The table is owned by `psychdeep_backend`, FORCE RLS is enabled, and direct `anon`, `authenticated`, and `service_role` grants are revoked. No end-user SQL access is used; the authenticated FastAPI endpoint enforces row ownership.
2. Generate a Fernet key with a trusted local Python environment that has `cryptography` installed:

   ```powershell
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Copy it into Render backend `psychdeep-api` → Environment → **LLM_USER_CREDENTIALS_KEY**. Store a recovery copy in your secrets manager; do not commit or paste it in chat/issue/PR/console logs. Do not re-generate this key after users have stored secrets without migrating/re-encrypting all ciphertext: they would become inaccessible.
3. Configure `MODEL_LOCAL_CF_ACCESS_HOST=ai.bfab.io` on the Render backend. `MODEL_LOCAL_BASE_URL=https://ai.bfab.io/v1` may remain the legacy default, but each user supplies their own matching endpoint in the form. Do not add cloudflared's tunnel token to Render or Supabase.
4. Keep `LLM_PERSONAL_MODE` absent or `false` while migrating. Deploy the new API and frontend together, and verify database schema checks, login, isolated GET/PUT/DELETE, encryption and CI. The existing global route is retained only for compatibility before cutover.

## Stage 3 — provision users and cut over

1. Each user signs into their own account and opens **Mis modelos**. For LM Studio, enter the approved URL, Cloudflare Access Client ID + Client Secret, LM Studio API token, and exact model ID. Save, then click **Probar mi conexión**. Each account can instead select Anthropic if permitted by deployment policy.
2. Check real end-to-end inference with TWO test accounts and distinct credentials: A's local selection must not alter B's Anthropic selection; A's token must never appear in B's headers, database responses, browser storage, logs or audit metadata. Test chat, diary analysis, crisis fallback, and the professional copilot. Also test missing keys, revoked Access token and disconnected Windows host.
3. Set `LLM_PERSONAL_MODE=true` only after the gate above. Redeploy backend. No configured account may fall back to global credentials or silently switch providers. Update health checks: the public process health is not a per-user provider availability test.
4. Once all accounts are migrated and rollback is no longer required, retire legacy global LLM/Access credentials and the old administrator-only provider-switch API in a separate cleanup. Keep audit history without storing secrets.

## Rollback and incident response

* Set `LLM_PERSONAL_MODE=false` to return to legacy routing **only as a deliberate, reviewed rollback**; this re-enables shared deployment credentials and should not be used if the personal model boundary is a security requirement. Alternatively disable LLM-dependent functionality and keep deterministic safety available.
* On compromise of a user's Access credential, revoke that service token in Cloudflare and the corresponding LM Studio key; have the owner rotate both in their own settings. On compromise of `LLM_USER_CREDENTIALS_KEY`, rotate all downstream user secrets and re-encrypt ciphertext using a controlled migration with the old key, after incident assessment.
* Never post live keys to GitHub, Render logs, support chats, screenshots, or frontend build variables (`VITE_*`).

## Release blockers

Do not merge this draft PR or deploy into clinical use until CI, database migration idempotency, cross-account authorization/inference tests, Cloudflare policies, encryption-key recovery and synthetic real-world end-to-end testing all pass. No production configuration or migration is performed by committing this document.

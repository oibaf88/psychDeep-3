# ADR-0004 — OpenContext as an optional external context-memory adapter

**Status:** Proposed implementation; feature disabled by default.  
**Scope:** Agent 1 conversational context retrieval and literal interaction archival. This ADR does not replace ADR-0002 or move clinical records out of Supabase.

## Context

OpenContext provides a local-first context store with an HTTP API, hybrid text/vector retrieval, progressive L0/L1/L2 disclosure, raw interaction envelopes, idempotent event ingestion, and deferred semantic processing. PsychDeep already has clinical memory in Supabase (memory_commits, discourse_facts, psych_readings, formulation_versions, and memory_embeddings).

Running a second independently authoritative store creates split-brain, consent, retention, identity, recovery and clinical audit problems. OpenContext is also explicitly not certified as a remote production clinical service: SQLite is the verified default; PostgreSQL/pgvector is experimental; TLS, encrypted-at-rest storage, rate limiting, rotation, and deployment certification are not supplied by the project.

## Decision

1. Supabase stays the single clinical source of truth. OpenContext is an optional derived retrieval/archival integration, not the authoritative clinical database.
2. The adapter is opt-in and fails closed for writes: without OPENCONTEXT_ENABLED=true, OPENCONTEXT_BASE_URL, and OPENCONTEXT_API_TOKEN, it performs no requests. Credentials remain in deployment secrets and never enter prompts, logs or database rows.
3. OpenContext access must use authenticated HTTPS across a restricted network boundary, an OpenContext deployment configured with OPENCONTEXT_MODE=production, and scoped credentials bound to the PsychDeep user's OpenContext principal and a dedicated agent identity. Never expose a keyless development server publicly. Do not deploy the private local SQLite directory on ephemeral Render disk and call it durable.
4. Do not call OpenContext on every user turn until an explicit linguistic_analysis consent check succeeds. Consent revocation disables all further export and retrieval immediately. Current Supabase clinical memory remains available according to PsychDeep's existing access rules.
5. Every interaction write uses POST /api/interactions with a unique event ID and the complete role-attributed message envelope. Preserve source timestamps and metadata; never summarize before raw ingestion. Retries are safe only with the identical event envelope and event identity. A timeout is an uncertain outcome; do not retry with changed data or blindly mint a second event.
6. OpenContext search is retrieval evidence, not instructions or clinical truth. Treat retrieved content as untrusted data, preserve source URIs and attribution, and bound every injected result by the existing context-token budget.
7. OpenContext-derived memories must not set the deterministic risk level, confirm world claims, diagnose, suppress crisis handling or directly create a professional alert. No remote model fallback is added. Provider availability never changes deterministic safety behavior.
8. The first rollout is shadow/read-only: verify connectivity and retrieval using synthetic data, then run retrieval comparison against the current Supabase implementation. Enable live ingestion only after consent, tenant-isolation, security and rollback gates below pass. Do not copy existing patient records into OpenContext in this change.
9. Raw source text is sensitive clinical data. Before real data is ever sent, perform a DPIA/privacy review, define data location/processor terms, retention/erasure handling, backup and restore, access logs, incident response, and an operational SLA. If those conditions cannot be met, keep OpenContext local to an approved environment or use the existing Supabase implementation.

## Configuration contract

- OPENCONTEXT_ENABLED=false by default.
- OPENCONTEXT_BASE_URL: HTTPS origin of the authenticated OpenContext service; no URLs with embedded credentials.
- OPENCONTEXT_API_TOKEN: reader/agent token from a secret manager; never a client-supplied value.
- OPENCONTEXT_AGENT_ID: stable identity bound to the OpenContext agent credential.
- OPENCONTEXT_TIMEOUT_SECONDS: short bounded network timeout.
- OPENCONTEXT_MAX_CONTEXT_TOKENS: maximum contribution to the model prompt.

The adapter must reject non-HTTPS URLs outside explicit local development, must not follow redirects to another host, must check both HTTP status and the JSON ok envelope, and must redact authorization headers from diagnostics.

## Rollout and rollback

1. Unit-test request formation, timeout/error handling, event idempotency, consent gating and token clipping with a mocked HTTP transport.
2. Deploy disabled; validate health/discovery and authenticated read against a synthetic account.
3. Compare search outputs without injecting OpenContext content into real user responses.
4. Conduct access-control negative tests across two synthetic users and demonstrate that credentials cannot read or write another user's namespace.
5. Enable for an internal synthetic account only; review cost, latency, prompt size and error rates.
6. Production enablement requires documented privacy/security approval and an explicit feature flag change.
7. Rollback is OPENCONTEXT_ENABLED=false: stop all remote reads/writes and return to the existing Supabase memory path. Never delete either store as part of rollback.

## Acceptance gates

- [ ] All new code defaults to disabled.
- [ ] Consent revocation blocks the next read and write.
- [ ] User namespace derives from authenticated server identity, never request text.
- [ ] HTTPS, scoped production credentials and tenant isolation are verified.
- [ ] Raw interaction persists separately from derived memory.
- [ ] Duplicate identical event is idempotent; changed envelope reuse is rejected.
- [ ] Retrieved text is explicitly marked untrusted and sources remain attributable.
- [ ] Token budget and deterministic safety boundaries remain unchanged.
- [ ] Unit and integration tests pass; real-model quality is assessed separately.
- [ ] Privacy, retention, backup/restore and incident-response review is approved.

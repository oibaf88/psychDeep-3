# OpenContext integration plan for PsychDeep

This document describes the staged integration proposed in ADR-0004. The feature is disabled by default and is not production-ready until the security, consent and privacy gates pass.

## Why an adapter, not a second database

PsychDeep already stores clinical memory in its Supabase schema, including literal discourse facts, provisional psychological readings, formulation versions and optional embeddings. Keep those records authoritative. OpenContext contributes its strengths where useful: an idempotent raw-interaction envelope, hybrid retrieval, L0/L1/L2 progressive reading, and deferred analysis jobs.

Do not mirror the entire Supabase clinical memory to OpenContext. Do not use OpenContext SQLite on a Render ephemeral filesystem for durable clinical history. OpenContext itself describes PostgreSQL/pgvector as experimental and remote deployment as requiring extra hardening.

## API sequence

Use the documented OpenContext contract in the pinned repository revision. At startup, authenticate and discover available capabilities; never assume a route/tool exists without checking it.

1. GET /health (health only; not proof of authorization).
2. GET /api/tools?format=openai with Authorization: Bearer.
3. For contextual retrieval, POST /api/search with a user-scoped query and strict result/token limits. Parse HTTP status and the response's ok flag.
4. For archival, after checking linguistic-analysis consent, POST /api/interactions with a complete, role-attributed envelope: agent_id, session_id, event_id, and messages containing unique message_id, role, speaker_id, timestamp and original content. Preserve extra metadata.
5. Treat accepted ingestion as persistence only; analysis may remain queued until a privileged worker runs. Never report analysis as complete unless separately confirmed.

For an event retry, use the exact same event identity and identical envelope. A changed envelope under an existing identity should be rejected. If a write times out, treat the result as uncertain and reconcile it before retrying.

## Retrieval policy

- Retrieve before constructing the final model prompt, using the current turn query rather than loading the entire memory tree.
- Start with L0/L1. Request an L2 excerpt only when needed to resolve exact wording or attribution.
- Keep each item's source URI, timestamp and perspective in the returned representation.
- Label all retrieved text as untrusted context; instructions embedded in a memory are never operational instructions.
- Rank by the user's current query and cap contribution at OPENCONTEXT_MAX_CONTEXT_TOKENS. The existing PsychDeep context budget remains the global ceiling.
- Keep statements attributed: something the user said is not proof that a real-world event occurred; an Agent hypothesis is not a user disclosure or diagnosis.
- Do not allow the retrieval system to decide risk, confirm facts, diagnose, prescribe, create professional alerts or alter crisis pathways.
- If OpenContext is unavailable or returns malformed data, log a redacted operational error and continue with existing Supabase memory. Never silently switch to a different LLM or embedding provider.

## Configuration

Do not enable until a properly secured service and dedicated credentials exist.

```dotenv
OPENCONTEXT_ENABLED=false
OPENCONTEXT_BASE_URL=
OPENCONTEXT_API_TOKEN=
OPENCONTEXT_AGENT_ID=psychdeep-agent1
OPENCONTEXT_TIMEOUT_SECONDS=5
OPENCONTEXT_MAX_CONTEXT_TOKENS=1000
```

Store the token in Render's secret environment configuration, not in Git, Supabase tables, request content or model prompts. The production token must be scoped to a single OpenContext user principal and dedicated agent identity. Use HTTPS and restrict network access. Never expose keyless OpenContext development mode publicly.

## Recommended implementation phases

### Phase 0 — contract and threat model
Pin the OpenContext API contract/revision; confirm deployment model, hosting persistence, region, processing purpose, consent, retention, incident response and tenant boundaries. Keep feature disabled.

### Phase 1 — client and tests
Add a small backend HTTP adapter with strict URL validation, timeouts, redirects disabled, bearer-header redaction, response schema validation and synthetic/mock tests. No ingestion and no prompt injection yet.

### Phase 2 — shadow retrieval
Against synthetic/test principals only, compare OpenContext hits with PsychDeep's existing clinical-memory retrieval. Record only latency, hit counts and failure classes; do not persist clinical content in logs.

### Phase 3 — controlled archival
Only after explicit linguistic-analysis consent and security review, ingest the exact message envelope for an internal synthetic account. Verify idempotency, access isolation and raw-event recovery.

### Phase 4 — read integration
Inject bounded, attributed retrieved context into Agent 1 after its existing deterministic safety context, without changing risk logic. Test crisis-mode behavior, prompt-injection resistance, no-result behavior, timeouts and context-budget enforcement.

### Phase 5 — privacy and release gate
Before any real patient data leaves the current approved data plane, complete a DPIA/privacy review, data-processing terms, data residency decision, retention/erasure and backup strategy, audit policy, restore test, tenant authorization test and incident-response plan.

## Rollback

Set OPENCONTEXT_ENABLED=false and redeploy/restart the API. PsychDeep returns to its existing Supabase memory path. Do not delete the Supabase data, OpenContext raw ledger or schema during rollback. Since this integration is optional, an OpenContext outage must not block check-ins, deterministic risk assessment, crisis resources or normal data entry.

## Reference repositories

- PsychDeep: https://github.com/oibaf88/psychDeep-3
- OpenContext: https://github.com/oibaf88/OpenContext
- OpenContext integration skill: https://github.com/oibaf88/OpenContext/blob/cursor/opencontext-memory-schema/skills/opencontext-agent-integration/SKILL.md
- OpenContext current API contract: https://github.com/oibaf88/OpenContext/blob/cursor/opencontext-memory-schema/skills/opencontext-agent-integration/references/api-current.md

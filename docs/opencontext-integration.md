# OpenContext and Longitudinal Memory Refactor

This document describes the integration path in ADR-0004 and the broader memory architecture in ADR-0005. Both features remain disabled/not wired to live patient traffic until the required privacy, security and validation gates pass.

## Current problem being addressed

PsychDeep already stores chat/diary source messages and a clinical-memory layer. Agent 1 currently constructs its context from recent messages, confirmed declarations, safety plan, check-ins, profile/open threads, psychosocial state, a small number of ranked discourse facts/readings and curated knowledge. The context has a budget, but the curated knowledge block can still contain every active, unexpired item. Deep longitudinal analysis and conversational recall should not be synonymous with placing as much historical text as possible into every prompt.

The target approach separates **retention**, **analysis** and **prompt context**:
- retain the original permitted source and provenance;
- derive typed memories, source-linked observations and versioned summaries asynchronously;
- retrieve the smallest evidence bundle that answers this turn's task;
- build the prompt from ranked, attributed material under a measured token budget.

## Data authority

Supabase stays the canonical clinical source of truth. The expand-only memory pipeline migration adds references, normalized memory items, layered summary versions, idempotent analysis jobs and retrieval telemetry without rewriting the legacy sources. The OpenContext service is optional and disabled by default; it must not become a second clinical truth store by accident.

No real patient data should be backfilled or exported by this proposal. OpenContext's own current documentation says SQLite is the verified default, Postgres/pgvector remains experimental, and a remote deployment does not include TLS termination, encrypted-at-rest storage, rate limiting, automatic key rotation or deployment certification by default.

## Adapter environment

\`\`\`dotenv
OPENCONTEXT_ENABLED=false
OPENCONTEXT_BASE_URL=
OPENCONTEXT_API_TOKEN=
OPENCONTEXT_AGENT_ID=psychdeep-agent1
OPENCONTEXT_TIMEOUT_SECONDS=5
OPENCONTEXT_MAX_CONTEXT_TOKENS=1000
OPENCONTEXT_ALLOW_LOCAL_HTTP=false
\`\`\`

Store the token only as a server-side secret. The remote service must use HTTPS, restricted network exposure and OpenContext's production credential policy. Loopback HTTP is permitted only for explicit local development.

Before any raw clinical text is sent:
1. check the current user's linguistic-analysis consent immediately before the operation;
2. derive the user's OpenContext principal from authenticated server-side identity;
3. preserve role, speaker identity, source timestamp and available metadata;
4. send the complete literal event envelope before any model-generated summary;
5. reuse the same event ID only for an identical retry; reconcile uncertain timeouts before any retry;
6. retain the canonical source inside PsychDeep and record the OpenContext sequence/hash in the appropriate audit metadata.

An ingestion response proves that the literal payload was persisted, not that asynchronous semantic analysis completed.

## Retrieval and context compilation

1. Determine the task class (ordinary conversation, longitudinal analysis, professional review, crisis, psychoeducation or copilot).
2. Retrieve by the current user query and authenticated namespace, not by a model-supplied user URI.
3. Prefer L0/L1 summaries and compact source-linked evidence. Request L2 only for exact wording, contradiction checking or human review.
4. Deduplicate the same memory item while retaining all its source references. Never silently remove a relevant contradiction or correction.
5. Keep the current user turn, deterministic safety instructions and critical state outside the memory competition for budget.
6. Attach perspective, attribution, time and uncertainty to retrieved items. A report is not proof of the world claim; a generated hypothesis is not a fact or diagnosis.
7. Enforce a task-specific memory budget inside the existing global context budget. Telemetry stores hashes, selected references, token counts and failure classes, not clinical prompt bodies.
8. If remote memory fails, continue with the existing Supabase path. The deterministic risk engine, crisis response and data entry do not wait on memory services.

## Asynchronous deep analysis

The intended workers consume idempotent jobs for item extraction, summary refresh, embedding, contradiction detection, longitudinal analysis and optional OpenContext synchronization. Workers must be retryable and versioned. A stored source message is not blocked on a model call; jobs can remain pending if no appropriate model deployment is available.

Generated summaries are cacheable projections, never replacements for their sources. Cache keys must include source digest, model/deployment, prompt/schema version and applicable consent revision. Re-embedding with a different model is a migration; vectors from incompatible embedding spaces must never be compared.

## Phases

- **Phase 0 — schema and contract:** map every existing source table and verify migration apply/re-apply, forced RLS and negative authorization tests.
- **Phase 1 — pipeline primitives:** validate typed memory items, provenance, context compilation, idempotency, token budgets and synthetic tests.
- **Phase 2 — ingestion and outbox:** queue work in the same transaction as source references where feasible; backfill references only when source identity is recoverable.
- **Phase 3 — workers:** incremental extraction, layered summaries, contradiction/temporal analysis, optional embeddings and retry/dead-letter handling.
- **Phase 4 — retrieval wiring:** shadow-build Agent 1 and professional-review contexts from the new compiler, compare against the current pipeline, then enable behind a feature flag.
- **Phase 5 — OpenContext staging:** synthetic-only service, scoped identity, tenant isolation, idempotent event ingestion and source recovery.
- **Phase 6 — controlled rollout:** after security/privacy approval, enable for an internal test account and gradually increase traffic while measuring retrieval coverage, clinical review quality, actual token counts, latency and cost.

## Rollback

Disable the relevant memory/OpenContext feature flags and restore the current Supabase memory compiler. Do not delete source data, summary history or canonical memory tables as part of rollback. OpenContext being offline must not impair core PsychDeep safety behavior.

## Release conditions

The schema and compiler foundation does not by itself mean the refactor is complete. Before live cutover, verify the full backend suite, database migration idempotency, RLS isolation, consent revocation, source traceability, source recovery after timeout/retry, prompt-injection handling, crisis behavior, backup/restore, data retention, privacy assessment and actual token savings measured against representative task benchmarks.

# ADR-0005 — Longitudinal memory architecture and token-efficient context

**Status:** Design proposal for staged implementation. Depends on ADR-0002 and ADR-0004.
**Goal:** Preserve the full relevant history while giving each model call only the smallest evidence-backed context needed for the current task.

## Core rule: retain broadly, retrieve narrowly

Persistence and prompt construction have different objectives. Store the original permitted event once, append derived records with provenance, and construct each model context from a ranked, task-specific evidence bundle. Never use a short prompt window as the only memory store; never stuff the whole database into the prompt.

## Target architecture

1. **Immutable-ish source ledger in Supabase:** canonical message/event rows (or references to existing chat/diary records), event ID, message ID, authenticated user, role/speaker, server receipt time, user timestamp/timezone when provided, channel, consent version, schema version, content hash, retention/access class and redaction state. Append corrections as new events; do not silently rewrite provenance.
2. **Normalized memory graph:** atomic discourse facts, world claims (unverified by default), preferences, episodes, open threads, goals/plans, clinical observations, longitudinal patterns, psychological hypotheses, contradictions/corrections and professional annotations. Every derived item records its source event/message IDs, model/prompt/schema version, created time, confidence/uncertainty, attribution, status, supersession link and consent basis.
3. **Layered summaries:** L0 compact orientation, L1 thematic summary, L2 evidence-rich details and references. Summaries are versioned projections, not replacements for source data. Rebuild or supersede them without deleting originals.
4. **Retrieval index:** lexical full-text search and vector search in the existing approved data plane, fused by reciprocal-rank or another measured ranker. Keep embeddings tied to deployment/model/version/dimension; never compare vectors from different spaces. If embeddings are unavailable, use lexical retrieval, not a silent provider switch.
5. **Temporal/longitudinal index:** event-time timelines, recurring themes, state changes, gaps in recorded data, contradictions, trajectory features and episodic clusters. A gap means “not recorded”, never “did not happen”. Clinical risk stays computed exclusively by the deterministic versioned risk engine.
6. **Context compiler:** assemble a typed evidence bundle for the exact task, remove duplicates, resolve superseded versions, retain contradictory views rather than picking one silently, order evidence by relevance/recency/importance/uncertainty, and enforce a global token budget.
7. **Async derivation pipeline:** outbox/job records, idempotent workers, bounded retries, dead-letter/error state, prompt/model/schema versioning and replay against synthetic fixtures. The user turn must not block on expensive deep analysis; ingestion is acknowledged separately from derivation completion.
8. **Observability:** token estimates/input tokens, context contribution by section, retrieval hits, source coverage, latency, embedding hit/miss, truncation decisions, duplicate rates, job failures and model versions. Never log clinical text or secrets merely to measure the pipeline.

## Context tiers by task

- **Ordinary conversation:** current user turn + recent turns + relevant L0/L1 + up to a few source-linked memories.
- **Longitudinal analysis:** query plan across timeline, source-linked episode clusters, contradictions and changes, relevant L2 excerpts. Paginate/chunk the source corpus and synthesize over compact intermediate notes; include citations to internal event IDs.
- **Clinical/professional review:** source excerpts, explicit attribution, evidence level, uncertainty, timestamps and annotation trail. No hidden generated summary without access to its evidence.
- **Crisis mode:** deterministic safety posture and current-turn facts first. Do not wait for OpenContext or semantic jobs; avoid exploratory narrative retrieval that distracts from immediate support.
- **General product/psychoeducation:** curated, current, reviewed knowledge retrieved by population/objective/locale/topic and contraindications, not every active knowledge item.

## Token-efficiency controls

- Define a single global budget across recent messages, patient state, clinical memory, OpenContext retrieval, curated knowledge and tool output.
- Reserve minimum budgets for the current turn and deterministic safety instructions; lower-priority context is dropped first.
- Use query-aware retrieval and small result counts; use L0/L1 by default and L2 only when exact wording or auditability matters.
- Deduplicate semantically similar chunks while retaining multiple source references and timestamps.
- Keep persistent summaries updated asynchronously and incrementally; do not regenerate the entire longitudinal formulation on every turn.
- Cache embeddings/summaries by content hash + model/prompt/schema/version + consent revision; invalidate precisely when source, consent or policy changes.
- Maintain separate model budgets for extraction, deep analysis, embeddings and conversational response. Expensive analysis is event-driven or scheduled, not a hidden call on every response.
- Use structured JSON for derived records with schema validation. Retry only transient, idempotent jobs; malformed outputs must not overwrite existing memory.
- Count actual model token usage when the provider exposes it; compare against a tokenizer estimate and adapt budgets from measurements.
- Measure quality with retrieval recall/source coverage and expert-reviewed longitudinal questions, not token reduction alone.

## Data contracts and proposed entities

This is a logical schema, not a migration script. Exact existing tables and identifiers must be mapped before migrations are authored.

- `memory_events`: stable event identity, user_id, session/channel, timestamps, consent/policy versions, content hash, raw payload/reference, idempotency key, ingestion state.
- `memory_messages`: event_id, message_id, role, speaker_id, literal content or secure source reference, timestamp, metadata, content hash.
- `memory_items`: typed atomic item, subject, perspective, attribution, content, confidence, uncertainty, temporal scope, source references, status/supersedes, sensitivity.
- `memory_summaries`: user_id, scope/topic/time range, L0/L1/L2, source watermark, version, model/prompt/schema and content hash.
- `memory_embeddings`: item/chunk reference, model/provider deployment, version, dimensions, vector and content hash. Enforce consistent dimensions/model space.
- `memory_retrieval_runs`: query/task class, selected item IDs/source IDs, ranker and embedding version, budget, actual tokens, latency, outcome; avoid storing raw query text when metrics do not require it.
- `memory_jobs`: event/type, idempotency key, attempts, next retry, status, error category, output provenance and dead-letter status.
- `memory_contradictions`: linked item IDs, type, status, resolution annotation and source references.
- `memory_consent_snapshots`: only where legally/architecturally appropriate; record consent version/reference needed for reproducibility, not an alternate consent authority.

Use foreign keys and indexes around user_id, event time, source IDs, item type/status, topic, hash and job status. Apply RLS to every patient-linked table, deny cross-user access by default, and test negative access paths. Large data should be partitioned only after measurements justify it.

## Relation to OpenContext

OpenContext may provide the raw-interaction ledger API, context filesystem abstraction, hybrid retrieval and progressive disclosure. During migration:
- Supabase remains the authoritative clinical store unless a separately reviewed ADR changes this.
- Do not write a second copy of all clinical tables blindly. Prefer a clearly declared projection or an explicit mirror with reconciliation/idempotency rules.
- OpenContext derived records need source IDs and import/export watermarks to prevent loops.
- The current OpenContext guide warns that SQLite immutability triggers are not tamper-proof against the database owner, PostgreSQL/pgvector is experimental and remote production hardening is incomplete. This must be resolved before storing real clinical data remotely.
- If the deployment cannot meet the data protection bar, implement the same retrieval/context patterns directly over Supabase and leave OpenContext local or synthetic-only.

## Migration approach

1. Inventory and map existing chat, diary, consent, clinical-memory, model-run and embedding records. Quantify duplicates/missing source IDs before DDL.
2. Add new schema expand-only, with RLS and indexes; preserve the v12 legacy source and existing canonical memory tables.
3. Backfill only traceable references and hashes first. Never invent missing speaker/timezone/source metadata.
4. Shadow-extract derived memories to a separate namespace and compare to current records using synthetic/redacted fixtures; no production prompt use yet.
5. Introduce query-aware context compilation behind a feature flag, compare answers/retrieval against existing Agent 1 context, then gradually ramp.
6. Move ingestion to the canonical event path only after consent, idempotency, restore and cross-user authorization tests pass.
7. Monitor quality, latency and actual token spend. Rollback means switch to existing Supabase context compiler; do not delete data/schema.

## Release gates

- No missing source provenance for derived memory.
- Unverified world claims remain unverified; hypotheses stay distinguishable from user reports.
- Consent revocation blocks future transfer, embedding and analysis.
- Tenant isolation and RLS negative tests pass.
- Deterministic safety output is unchanged by vector retrieval or LLMs.
- Deep analysis is reproducible from source IDs and model/prompt/schema versions.
- Actual token consumption and longitudinal retrieval quality are measured on a representative synthetic benchmark.
- Backup, restore, retention and authorized professional access are tested.

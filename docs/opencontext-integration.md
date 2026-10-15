# OpenContext and whole-person longitudinal memory

This integration uses selected OpenContext patterns — literal event envelopes, progressive L0/L1/L2 disclosure, query-aware retrieval and deferred processing — to strengthen PsychDeep's own longitudinal clinical memory. Supabase remains the canonical clinical data store.

## Why this is more than conversational recall

The goal is to build a revisable, evidence-linked understanding of the patient over time: life context, relationships, health/treatment, recovery when relevant, emotional experience, coping, values, goals, routines, social conditions, strengths, recurring episodes, trajectories, contradictions and relevant unknowns. This is not created by putting an entire transcript in every prompt. Original records are retained, episodes are consolidated in bounded batches, higher-level digests are cached, and each task retrieves a bounded evidence bundle from that hierarchy plus source-linked records.

See ADR-0005 for the token/context design and ADR-0006 for the whole-person model, epistemic rules and rollout gates.

## Longitudinal pipeline

1. **Canonical source:** the original chat message, diary entry, check-in, structured observation, confirmed fact, intervention or human annotation stays in its current authoritative table.
2. **Consent-aware event ledger:** register the source reference, content hash, event time and consent snapshot. It does not create another transcript copy.
3. **Temporal episodes:** a background worker reads raw chat/diary rows as well as derived observations and groups material into bounded monthly batches. Every source reference must be accounted for exactly once per batch, with unassigned references reported explicitly.
4. **Hierarchical digests:** if the history has more than 80 active episodes, bounded groups of at most 12 adjacent episodes/digests are consolidated into versioned L0/L1/L2 time-window summaries. Stable source digests let later runs reuse completed nodes and continue only unfinished work.
5. **Whole-person model:** a structured synthesis consumes the full digest hierarchy, recent higher-detail episodes, current structured measures, source-linked memories, prior hypotheses and counterevidence. Each facet, pattern, trajectory, protective factor, contradiction, recording gap and open question must reference known evidence.
6. **Projections:** the model is published as a versioned patient_model_versions row, searchable memory_items and a global L0/L1/L2 summary. Previous projections are superseded, not overwritten as historical truth.
7. **Query time:** Agent 1 can use the bounded patient model plus a small number of indexed historical source passages relevant to the current query. This does not run full-history synthesis on every user turn.

The tree is auditable: a higher-level summary points to child summary or episode IDs; episodes point to source IDs; canonical source tables hold the original text and structured observations.

## Epistemic rules

- User report, professional report, third-party report, system observation, assistant hypothesis and derived pattern remain distinct.
- A user statement is evidence of what was said, not automatic proof of a world event.
- A psychological hypothesis is not a diagnosis. A recurring pattern needs multiple source records and uncertainty.
- Contradictions and corrections remain inspectable; the newest statement does not automatically erase an older one.
- A missing record is a recording gap, not proof that an event, symptom or relationship state was absent.
- Temporal association does not establish causality. Protective-factor availability can be historical or unclear, not assumed current.
- The deterministic risk engine remains the only risk-level authority. Crisis replies bypass exploratory biography retrieval and preserve fixed safety logic.
- When consent is revoked, new purpose-bound extraction, synthesis and retrieval stop. Jobs are cancelled rather than retried.

## Token efficiency

A single global context budget includes recent turns, current state, legacy clinical memory, the patient model, historical excerpts, curated knowledge and tool output. The longitudinal query path uses PostgreSQL full-text indexes on atomic memory items, episode/digest summaries, discourse facts and raw user/diary source text. The SQL retrieval is user-scoped and bounded; raw passages are returned as short excerpts, not complete conversations.

The whole-person patient model and query retrieval serve different functions. The model provides compact longitudinal orientation and patterns; retrieval supplies specific historical passages for checking those patterns against original evidence. The retrieval feature flag remains off during initial shadow evaluation:

- MEMORY_PIPELINE_CONTEXT_ENABLED=false (current safe default).
- MEMORY_PIPELINE_CONTEXT_BUDGET_TOKENS=800 (maximum addition for query-driven retrieval when enabled).

The feature can be enabled only after migrations and privacy/security checks pass, and retrieval quality/cost have been compared with the existing prompt path. No token-savings claim is made until actual provider usage is measured.

## Worker and deployment

The background worker is a separate process, not part of the patient-facing chat request. Run it from the backend directory with the same approved database and model-gateway secrets:

    python scripts/run_memory_worker.py --limit 1

A Render Background Worker or scheduled job can invoke it repeatedly. Each invocation claims an idempotent queued job, processes a bounded number of episodes/digest groups, records model/run provenance and enqueues a continuation if more work remains. The patient-facing response must never wait for deep synthesis.

The OpenContext adapter remains disabled unless explicitly configured. Before any real content is exported, an authenticated HTTPS deployment with scoped tenant-bound credentials, persistent storage, retention/erasure, backups, access logs, incident response and privacy review must be in place. The initial design does not backfill or duplicate production patient records into OpenContext.

## Validation gates

- Apply/re-apply all migrations in the supported Supabase role model; verify forced RLS and tenant-isolation negative tests.
- Run the backend suite, frontend checks/build and Docker images.
- Test synthetic histories containing hundreds/thousands of sources, a long single message, late-arriving historical sources, explicit corrections, contradictory reports and recording gaps.
- Verify that each raw source is reachable through the hierarchy, every digest output source ref is valid, job retries do not duplicate active episodes and consent revocation cancels future processing.
- Compare historical-question retrieval against the legacy context using source coverage, expert review, response quality, actual token counts, latency and cost.
- Verify backup/restore, retention/erasure and security before enabling real clinical traffic or OpenContext export.

## Rollback

Set MEMORY_PIPELINE_CONTEXT_ENABLED=false and disable the OpenContext feature. The app falls back to existing clinical memory and deterministic safety behavior. Do not delete source data, summary versions, memory history or the patient-model version trail as part of rollback.

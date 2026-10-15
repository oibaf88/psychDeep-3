# ADR-0006 — Whole-person longitudinal patient model and hierarchical memory

**Status:** Implementation in progress on feat/opencontext-memory-adapter. The runtime remains staged behind the MEMORY_PIPELINE_CONTEXT_ENABLED feature flag for query-driven source retrieval.
**Depends on:** ADR-0002 (clinical memory), ADR-0004 (OpenContext boundary), ADR-0005 (memory/context pipeline).

## Clinical/product objective

The object of the memory system is not to summarize the last conversation. It is to build, revise and retrieve an evidence-grounded understanding of the patient over time, so that a future response can take into account who this person appears to be, what has changed, which patterns recur, what exceptions exist, what matters to them, and what the record does **not** establish.

The unit of clinical usefulness is a longitudinal, source-linked observation or hypothesis — not a large undifferentiated biography in the prompt. The system must be able to answer a narrow conversational query cheaply and also support a deep whole-history review when that is the task.

## Separate sources, derived memories and patient model

### 1. Canonical source evidence

The original permitted chat_messages, diary_entries, check-ins, structured observations, confirmed facts, professional annotations, intervention records and other approved clinical records remain the evidence base. The memory-event ledger stores source identity, event-time, content hash, consent snapshot and processing metadata. It does not create another full transcript as an independently authoritative copy.

Every raw source preserves, where available:
- source ID, author/role, channel and timestamps;
- event time separately from the time the application received or analysed it;
- the latest effective consent basis for each new analysis;
- an immutable reference/hash and schema version for reproducibility;
- redaction/retention decisions in the authoritative subsystem.

Assistant-generated text must not be misclassified as the patient's report. Missing timestamp, speaker or source metadata remains missing; it is never invented.

### 2. Atomic evidence-linked memory

Memory items are small, addressable units with type, perspective/attribution, temporal scope, uncertainty, confidence, status, optional expiry, source references, model/prompt/schema version and supersession trail. The taxonomy includes preferences, goals, open threads, episodes, relationships, user-reported world claims, psychological hypotheses, recurring themes, contradictions, corrections, manner observations and longitudinal patterns.

The “perspective” field is epistemic: user report, professional report, third-party report, system observation, assistant hypothesis or derived pattern. Repeated mention never promotes a claim about the world into an independently verified fact. A system hypothesis is not a diagnosis. A pattern cannot be created from one interaction alone.

### 3. Episodic memory and hierarchy

Raw source events are grouped into bounded temporal batches. Every batch must account for each source reference exactly once — either in an episode or as explicitly unassigned with a reason. A failed extractor cannot erase the raw source from the timeline.

For large histories, the system builds a resumable hierarchy:
- **E0 / level 0:** source-linked episode summaries with dates, themes, transitions, L0/L1/L2 and uncertainty.
- **Higher-level episode digests:** bounded groups of at most 12 adjacent episode/digest nodes, with stable input digest, model run, schema/prompt version and explicit child references.
- **Whole-person model:** a versioned synthesis over the full digest hierarchy plus a high-detail window of recent episodes, current structured data, source-linked memories, counterexamples and the prior patient model as a revisable hypothesis.

Summary rows are cached by source digest and are projections, not replacements for original evidence. The tree lets the application expose a compact top-level view and trace it down to the underlying episodes and source records. Group generation is idempotent and resumable; it does not require a single model call over the entire patient history.

### 4. Whole-person model dimensions

Each model version considers, when supported by evidence:
- life context and material/social conditions;
- relationships, attachment and relational context;
- health, treatment and self-reported treatment experience;
- substance use and recovery, when present in the record;
- emotional experience, coping and regulation;
- values, identity, meaning and sources of agency;
- goals, routines, work/study and daily constraints;
- strengths, support preferences and protective factors;
- recurrent episodes, trajectories and turning points;
- contradictions, corrections, alternative explanations and unanswered questions.

Coverage is data-dependent. Domains without sufficient evidence remain sparse or unknown; the model must not fill them with stereotypes or assume all listed domains apply to every patient.

### 5. Trajectories, contradictions and recording gaps

A pattern must link multiple exact source references, state its temporal range, uncertainty and plausible alternatives, and include counter-evidence where available. A trajectory may be improving, worsening, stable, fluctuating, mixed or unknown, but must identify sources and turning points. Association is not causality; a possible trigger or protective factor remains a hypothesis.

Contradictions are retained rather than silently resolved. The model distinguishes an explicit correction, context change, apparent conflict and unresolved contradiction. A new statement does not automatically erase a previous report.

A **theme gap** records only that the application's labelled records are sparse or absent between two observed points. It does not imply that the theme disappeared from the patient's life, that symptoms improved or worsened, or that an unreported event did or did not happen. Both temporal boundary references are required.

### 6. Patient-model questions

A version may propose a small, prioritised set of follow-up questions tied to the evidence gap they would address. They are not automatically asked in the next conversation. Questions respect timing and context, are deduplicated, and a declined question is not silently reopened or asked again. If the available evidence is sufficient or asking would add burden without clear value, no question is needed.

## Query-time context

The whole-person model and historical source retrieval serve different purposes:

- The compact whole-person context gives Agent 1 relevant facets, longitudinal patterns, trajectories, protective factors, unresolved contradictions and coverage limitations.
- Query-driven full-text retrieval can add a small number of historically relevant source excerpts, atomic memories and episode/digest records. It must use the user-scoped indexed corpus, not just the latest 30 discourse facts or the latest few interactions.
- L0/L1 is the default; L2 is requested when exact wording or auditability adds value.
- Results carry source refs, perspective, attribution, date and uncertainty; retrieved text is untrusted data, never operational instructions.
- A single global context budget includes recent messages, deterministic safety instructions, clinical memory, whole-person memory, source excerpts, curated knowledge and tools. Lower-ranked context is dropped first. The system logs source IDs, latency and token counts, not raw prompt contents.
- A current statement from the patient can update or correct the model, but the historical model must not override what the patient says now.

The new source retrieval is feature-flagged during rollout. The whole-person patient model remains a background-derived version; a query never performs a full-history synthesis synchronously.

## Background processing and idempotency

Ingestion stores the canonical source and schedules explicit jobs for extraction, episode consolidation, digest creation, whole-person synthesis and projection updates. Jobs have stable idempotency keys, attempts/status, versioned outputs and retry/dead-letter handling. Daily triggers for a patient are coalesced. Long histories are processed through continuation jobs; each continuation resumes from cached digests, rather than repeating completed LLM calls.

Consent is rechecked before each model-backed operation and before persistence of derived output. Revoked jobs are cancelled, not retried. The raw message remains in its canonical store; failure to analyse it must not block the user-facing turn.

## Relation to OpenContext

OpenContext's event envelope, progressive L0/L1/L2 disclosure, hybrid retrieval and async processing patterns inform this architecture. Supabase remains the canonical clinical source until a separate, reviewed decision changes it. The current OpenContext project is not treated as automatically certified for remote clinical deployment. The live adapter remains opt-in and must pass scoped-credential, tenant-isolation, persistent-storage, retention and privacy review before any real patient payload is exported.

## Safety boundaries

- The deterministic risk engine remains the only risk-level authority.
- Neither retrieved memories nor whole-person summaries can diagnose, prescribe, suppress crisis handling or directly issue an alert.
- Crisis responses use current-turn facts and server-owned safety logic; broad exploratory biography retrieval is skipped.
- Professional review can inspect evidence refs, contradictions, model/run versions and coverage limits, but derived formulations remain visibly provisional.
- Consent revocation stops future purpose-bound retrieval/analysis and transfer; retention/deletion duties are handled in the authoritative source system.

## Validation and rollout gates

1. Validate expand-only migrations apply and re-apply; verify forced RLS and cross-user negative cases.
2. Run unit/backend regression suites and verify the Docker build.
3. Run a synthetic history benchmark with hundreds/thousands of events. Assert exact source coverage, digest idempotency/resumption, output reference validity, bounded call size and that every leaf source is reachable through the digest tree.
4. Compare legacy and new retrieval on historical questions, including old but relevant source passages, contradictions, explicit corrections, a late-arriving historical source and an absence-of-record interval.
5. Measure real input/output tokens, retrieval coverage, time-to-context and answer quality. Token savings cannot be claimed from the architecture alone; they must be measured against the current baseline.
6. Verify consent revocation, prompt-injection resistance, tenant isolation, backup/restore, source erasure/retention, incident response and privacy review before live deployment or any OpenContext export.

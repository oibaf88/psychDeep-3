# ADR-0001 — Cloud-first clinical source of truth + replaceable Model Gateway

Status: Accepted for vNext baseline

## Context

The previous implementation expanded the optional local-model path into a second local frontend/API/PostgreSQL stack with bidirectional SymmetricDS replication. That increased clinical state ambiguity, conflict handling, secret surface and operational complexity without improving the central product objective: individual longitudinal change, self-regulation, explainability and human collaboration.

## Decision

1. Supabase/PostgreSQL in cloud is the only authoritative clinical data store.
2. Render hosts the current web/API prototype; domain boundaries remain provider-neutral.
3. The only optional local runtime is an OpenAI-compatible LLM plus authenticated outbound HTTPS tunnel when cloud API access is required.
4. Every generative deployment is selected by a stable server-side alias through `ModelGateway`.
5. Model availability cannot alter consent, storage, audit or deterministic risk semantics.
6. There is no silent primary/fallback provider chain.
7. Endpoint URLs/credentials are operations secrets, not clinical configuration.
8. The historical offline/sync implementation is preserved on `past/local-offline-sync-20260913` but removed from the production path.

## Consequences

Positive: one clinical truth, simpler security model, reproducible safety, provider/model portability, lower prototype cost and fewer sync failure modes.

Trade-off: local-model availability depends on the trusted model host/tunnel. Model-dependent UX must therefore degrade safely; this is acceptable because safety/data functions are model-independent.

## Rollback

Application can roll back to a previous cloud release because database migration is expand-only. Re-enabling local clinical DB/sync is not the rollback strategy.

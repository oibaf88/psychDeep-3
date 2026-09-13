# ADR-0001 — Cloud-first clinical source of truth + replaceable Model Gateway

Status: Accepted for vNext baseline; amended 2026-09-13 for audited runtime model selection

## Context

The previous implementation expanded the optional local-model path into a second local frontend/API/PostgreSQL stack with bidirectional SymmetricDS replication. That increased clinical state ambiguity, conflict handling, secret surface and operational complexity without improving the central product objective: individual longitudinal change, self-regulation, explainability and human collaboration.

vNext still requires a replaceable LLM boundary, but the product owner also requires the clinical-administration profile to be able to switch explicitly between the approved Anthropic provider and the approved local/OpenAI-compatible endpoint without redeploying the application.

## Decision

1. Supabase/PostgreSQL in cloud is the only authoritative clinical data store.
2. Render hosts the current web/API prototype; domain boundaries remain provider-neutral.
3. The only optional local runtime is an OpenAI-compatible LLM plus authenticated outbound HTTPS tunnel when cloud API access is required.
4. `MODEL_DEPLOYMENT_ALIAS` defines the deployment default. When `LLM_ALLOW_RUNTIME_OVERRIDE=true`, only `admin_clinical` may explicitly supersede that default with an approved Anthropic or OpenAI-compatible deployment through the audited Settings flow.
5. Model availability cannot alter consent, storage, audit or deterministic risk semantics.
6. There is no silent primary/fallback provider chain. A provider change is always an explicit administrative action.
7. Model credentials remain server-side deployment secrets and are never stored in runtime-selection rows or returned to the browser. A local model endpoint URL may be edited only by `admin_clinical`, is validated for cloud reachability/HTTPS before activation, and is redacted from non-admin users.
8. Runtime selections are append-only audit history: the old selection is deactivated rather than overwritten.
9. The historical offline/sync implementation is preserved on `past/local-offline-sync-20260913` but removed from the production path.

## Consequences

Positive: one clinical truth, simpler security model, reproducible safety, provider/model portability, explicit operational control, lower prototype cost and fewer sync failure modes.

Trade-off: local-model availability depends on the trusted model host/tunnel. Model-dependent UX must therefore degrade safely. Allowing an administrator to change the compatible endpoint adds an SSRF/configuration surface, so production accepts only HTTPS/routable targets and keeps credentials outside the database/browser.

## Rollback

Application can roll back to a previous cloud release because database migration is expand-only. Model rollback is an explicit audited provider selection or reset to the deployment default. Re-enabling local clinical DB/sync is not the rollback strategy.

# psychDeep-vOG — agent contract

## Mission
Build a source-linked, longitudinal self-regulation and clinical collaboration platform. It supports understanding and review; it is not an autonomous clinician, diagnostic engine or substitute for deterministic safety logic.

## Start here
1. Root `AGENTS.md` and the current product specification.
2. `ARCHITECTURE.md`, `DATA_PRESERVATION.md`, `IMPLEMENTATION_PLAN.md`, `CLINICAL_VALIDATION.md` and `OPERATIONS_RUNBOOK.md`.
3. The relevant ADRs, API schemas, database migrations and tests.

## Hard constraints
- Preserve every existing clinical source row, stable identifier, timestamp, consent, audit trail, provenance link and historical version.
- Do not drop/recreate tables, truncate tables, reset production, or replace source records with generated summaries.
- Keep current Supabase production project/schema as the source of truth until a separately approved migration passes parity and rollback gates.
- Derived models are versioned projections. Publish a new active version only after complete validation and persistence; retain the last good version on failure.
- Enforce linguistic-analysis consent before and after external model calls. Do not log clinical text, prompts, outputs, credentials or exception messages.
- Keep risk and crisis decisions deterministic and independent from LLM outputs.
- Never replay dead-letter jobs, deploy or merge production changes automatically.

## Implementation standard
- Define/version every external and internal contract.
- Make jobs idempotent under duplicate delivery and safe after process restart.
- Validate exact source coverage and reject unknown references.
- Use bounded retries, explicit dead-letter states, correlation IDs and safe frame-only exception telemetry.
- Include backend and frontend regression tests, negative authorization tests and a data-preservation test plan.
- Represent loading, stale, partial, failed, consent-required and no-evidence states distinctly.
- Every inferred statement must expose perspective, uncertainty, provenance and source references.

## Daily agents/bots
Daily agents may produce a non-PHI operational report from aggregate telemetry and CI: error categories, code locations, retry/dead-letter counts, oldest pending job, freshness of last successful model, API/UI contract status, test status and open work. They may propose tickets/patches. They must not inspect patient text, change consent, replay jobs, alter production data, change environment secrets or deploy without a human-approved runbook.

## Definition of done
- Tests and checks are named with results; unknown/unrun checks are stated as such.
- Source rows and historical versions remain unchanged.
- A failed rebuild cannot replace the last good model.
- Memory is visible only to the patient or an assigned authorised professional.
- Rollback and recovery instructions exist.
- A human reviewer approves clinical interpretation changes and production rollout.

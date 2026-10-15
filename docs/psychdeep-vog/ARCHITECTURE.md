# psychDeep-vOG architecture

## System of record
The existing Supabase PostgreSQL project and `psychdeep_v12` schema remain the sole production clinical source of truth. Render hosts the web frontend and API/worker. Model providers sit behind the existing provider-neutral Model Gateway. A provider outage must not disable source storage, deterministic safety processing or access to the last successful memory version.

## Logical flow
```text
Canonical sources
  chat / diary / check-ins / confirmed facts / observations / professional notes
       |
       v
Consent + authorisation gate
       |
       v
Idempotent job queue -> bounded extraction/episode batches
       |                     |
       |                     +-> strict schema + exact source-ref coverage
       v
Versioned evidence tree -> whole-person synthesis
       |
       v
Validate provenance, uncertainty, schema, consent and freshness
       |
       v
Atomic publish of new version (only after all checks pass)
       |
       +-> patient profile / therapist memory / session preparation / agents
```

## Memory layers
1. **Source records:** immutable from the memory pipeline's perspective; normal user/clinician correction flows retain their own audit history.
2. **Derived episodes:** source-linked, temporally bounded, uncertainty-labelled and supersedable.
3. **Hierarchical summaries:** digest-keyed, versioned, resumable and linked to child nodes.
4. **Whole-person model:** provisional, versioned, source-validated and never equivalent to diagnosis or risk.
5. **Task context:** budgeted read-only compilation for a specific authorised agent/task; retrieved text is untrusted evidence, not instructions.

## Publication and consistency
A build has a correlation ID, source watermark, prompt/schema versions, digest, status and error category. The last good active model remains available until the candidate is fully validated and persisted. Partial processing must be visible and must not be reported as fresh success. Late-arriving or corrected sources invalidate relevant derived digests and trigger a bounded rebuild without rewriting source rows.

## API and UI contract
Expose version ID, generated-at time, source watermark, status, limitations, provenance and whether the version is stale. Distinguish `ready`, `processing`, `partial`, `failed`, `consent_required`, `consent_revoked` and `no_source_evidence`. The therapist view must verify assignment-level authorisation on every read and must not leak data to unassigned professionals or administrative roles.

## Deployment
Use a review branch and CI first. Production remains attached to the existing database and service URLs during the branding/repair phase. No production replay or deploy occurs as a side effect of a documentation or code change.

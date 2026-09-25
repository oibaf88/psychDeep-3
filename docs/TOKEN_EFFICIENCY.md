# Token-efficient longitudinal conversations

PsychDeep keeps the patient's complete history in persistent storage, but the
LLM never receives the complete history by default.

## Runtime policy

- Stored history is immutable from the context-budget layer.
- Agent 1 receives a bounded recent-message window.
- Agent 1 receives a bounded deterministic context block.
- The latest user turn is retained when a budget is tight.
- Normal conversational output is capped separately from clinical analysis.
- Anthropic chat requests cache the stable system-policy prefix while leaving
  per-turn patient context dynamic.
- Provider usage remains the billing source of truth; the application also
  records the context budget and estimated request size without storing
  patient text in the usage ledger.

## Default budgets

| Budget | Default |
| --- | ---: |
| Total conversational context budget | 12,000 estimated tokens |
| Recent conversation budget | 4,000 estimated tokens |
| Structured Agent 1 context budget | 6,500 estimated tokens |
| Recent messages | 12 maximum |
| Normal conversational output | 1,536 tokens |

The estimator is deliberately provider-neutral (approximately 4 characters per
token) and is only used to prevent unbounded requests. Provider-reported usage
remains authoritative for billing and reconciliation.

## Why this is safe

The refactor does not delete messages, facts, check-ins, profiles, risk
assessments or audit records. It only controls what is selected for a single
generative request. Deterministic safety evaluation remains independent of
the conversational model.

Longitudinal memory can therefore grow indefinitely in storage without
forcing the prompt to grow linearly with it.

## Next evolution

The architecture leaves room for a later retrieval layer over approved,
versioned longitudinal memory. That layer should select evidence relevant to
the current turn under the same context budget rather than increasing the
budget when the patient's history grows.

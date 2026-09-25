"""Token-aware context budgeting for longitudinal patient conversations.

The clinical history may grow without bound, but a single LLM request must not.
This module deliberately uses a provider-neutral conservative estimator so the
budget works before a provider-specific tokenizer is available. Actual usage
reported by the provider remains authoritative in the usage ledger.

Design goals:
- never replay the full conversation history;
- preserve the newest turns first;
- keep deterministic clinical context bounded;
- make truncation explicit and auditable;
- keep the total conversational input under a configurable ceiling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


DEFAULT_CHARS_PER_TOKEN = 4.0


def estimate_tokens(text: str | None) -> int:
    """Conservative, provider-neutral token estimate."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / DEFAULT_CHARS_PER_TOKEN))


def truncate_text(text: str, max_tokens: int) -> str:
    """Bound text while preserving both its beginning and end."""
    if max_tokens <= 0:
        return ""
    if estimate_tokens(text) <= max_tokens:
        return text

    max_chars = max(32, int(max_tokens * DEFAULT_CHARS_PER_TOKEN))
    if len(text) <= max_chars:
        return text

    head = max_chars // 2
    tail = max_chars - head
    return (
        text[:head].rstrip()
        + "\n[… contexto recortado por presupuesto de tokens …]\n"
        + text[-tail:].lstrip()
    )


@dataclass(frozen=True)
class ContextBudgetResult:
    messages: list[dict[str, str]]
    estimated_tokens: int
    truncated: bool


def fit_recent_messages(
    messages: list[dict[str, str]],
    max_tokens: int,
    *,
    max_messages: int = 12,
) -> ContextBudgetResult:
    """Keep the most recent complete turns that fit the budget."""
    if not messages or max_tokens <= 0:
        return ContextBudgetResult([], 0, bool(messages))

    candidates = messages[-max_messages:]
    selected: list[dict[str, str]] = []
    used = 0
    truncated = len(candidates) < len(messages)

    for message in reversed(candidates):
        content = str(message.get("content") or "")
        role = str(message.get("role") or "user")
        cost = estimate_tokens(content)
        if used + cost <= max_tokens:
            selected.append({"role": role, "content": content})
            used += cost
            continue

        remaining = max_tokens - used
        if remaining > 32 and not selected:
            bounded = truncate_text(content, remaining)
            selected.append({"role": role, "content": bounded})
            used += estimate_tokens(bounded)
        truncated = True
        break

    selected.reverse()

    if messages and messages[-1].get("role") == "user":
        latest = messages[-1]
        if not selected or selected[-1] != latest:
            bounded = truncate_text(str(latest.get("content") or ""), max_tokens)
            selected = [{"role": "user", "content": bounded}]
            used = estimate_tokens(bounded)
            truncated = True

    return ContextBudgetResult(selected, used, truncated)


def fit_context_block(
    sections: list[str],
    max_tokens: int,
) -> tuple[str, int, bool]:
    """Pack context sections in priority order under one token ceiling."""
    if max_tokens <= 0:
        return "", 0, bool(sections)

    selected: list[str] = []
    used = 0
    truncated = False

    for section in sections:
        if not section:
            continue
        cost = estimate_tokens(section)
        if used + cost <= max_tokens:
            selected.append(section)
            used += cost
            continue

        remaining = max_tokens - used
        if remaining > 64:
            bounded = truncate_text(section, remaining)
            selected.append(bounded)
            used += estimate_tokens(bounded)
        truncated = True
        break

    if len(selected) < len([s for s in sections if s]):
        truncated = True

    return "\n\n".join(selected), used, truncated

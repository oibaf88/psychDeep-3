"""Request-scoped context-budget telemetry.

The provider adapters remain unaware of patient/domain objects. This context
variable lets the existing usage ledger record how the conversational budget
was applied without putting clinical text into the ledger.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class ContextBudgetTelemetry:
    budget_tokens: int
    estimated_input_tokens: int
    message_count: int
    truncated: bool


_current: ContextVar[ContextBudgetTelemetry | None] = ContextVar(
    "psychdeep_context_budget",
    default=None,
)


@contextmanager
def record_context_budget(
    *,
    budget_tokens: int,
    estimated_input_tokens: int,
    message_count: int,
    truncated: bool,
) -> Iterator[None]:
    token = _current.set(
        ContextBudgetTelemetry(
            budget_tokens=budget_tokens,
            estimated_input_tokens=estimated_input_tokens,
            message_count=message_count,
            truncated=truncated,
        )
    )
    try:
        yield
    finally:
        _current.reset(token)


def current_context_budget() -> ContextBudgetTelemetry | None:
    return _current.get()

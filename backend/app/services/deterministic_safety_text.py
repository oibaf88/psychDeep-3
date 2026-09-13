"""Narrow deterministic safety-text rules.

This is intentionally conservative. It only promotes explicit first-person
self-harm/planning declarations that a user directly typed. Ambiguous phrases
stay outside this detector and may be explored conversationally or reviewed by
humans. The output is not a diagnosis and never calls an LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import ConfirmedFact


@dataclass(frozen=True)
class ExplicitSafetyDeclaration:
    category: str
    rule_id: str


# Explicit first-person formulations only. Word boundaries and bounded gaps
# reduce accidental matches such as quoting a film/article or saying that a
# different person is suicidal. Negation is checked separately.
_DIRECT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("SAFETY_TEXT_DIRECT_SUICIDE_01", re.compile(r"\b(?:quiero|voy\s+a|pienso)\s+(?:suicidarme|matarme)\b", re.I)),
    ("SAFETY_TEXT_DIRECT_SUICIDE_02", re.compile(r"\b(?:quiero|voy\s+a)\s+quitarme\s+la\s+vida\b", re.I)),
    ("SAFETY_TEXT_DIRECT_SUICIDE_03", re.compile(r"\bme\s+voy\s+a\s+(?:suicidar|matar)\b", re.I)),
    ("SAFETY_TEXT_DIRECT_SUICIDE_04", re.compile(r"\btengo\s+intenci[oó]n\s+de\s+(?:suicidarme|matarme|quitarme\s+la\s+vida)\b", re.I)),
)
_PLAN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("SAFETY_TEXT_PLAN_01", re.compile(r"\btengo\s+(?:ya\s+)?un\s+plan\s+para\s+(?:suicidarme|matarme|quitarme\s+la\s+vida)\b", re.I)),
    ("SAFETY_TEXT_PLAN_02", re.compile(r"\bhe\s+planeado\s+(?:c[oó]mo\s+)?(?:suicidarme|matarme|quitarme\s+la\s+vida)\b", re.I)),
)
_NEGATED = re.compile(
    r"\b(?:no|nunca|jam[aá]s)\s+(?:quiero|voy\s+a|pienso|tengo\s+intenci[oó]n\s+de)\s+(?:suicidarme|matarme|quitarme\s+la\s+vida)\b",
    re.I,
)
_QUOTING = re.compile(r"\b(?:dice|dijo|dec[ií]a|escribi[oó]|ley[oó]|pel[ií]cula|libro|noticia)\b.{0,50}\b(?:suicidarme|matarme|quitarme\s+la\s+vida)\b", re.I)


def classify_explicit_declaration(text: str) -> ExplicitSafetyDeclaration | None:
    candidate = " ".join((text or "").strip().split())
    if not candidate or _NEGATED.search(candidate) or _QUOTING.search(candidate):
        return None
    for rule_id, pattern in _PLAN_PATTERNS:
        if pattern.search(candidate):
            return ExplicitSafetyDeclaration(category="planning", rule_id=rule_id)
    for rule_id, pattern in _DIRECT_PATTERNS:
        if pattern.search(candidate):
            return ExplicitSafetyDeclaration(category="ideation_active", rule_id=rule_id)
    return None


def materialize_user_declaration(db: Session, user_id, text: str) -> ConfirmedFact | None:
    """Persist an explicit user declaration as a user-originated fact.

    The user has directly made the declaration; the server only assigns the
    narrow category required by the deterministic safety engine. The LLM is
    not involved. Exact duplicates are suppressed to avoid creating multiple
    facts when a client retries the same request.
    """
    declaration = classify_explicit_declaration(text)
    if declaration is None:
        return None
    content = (text or "").strip()[:4000]
    existing = (
        db.query(ConfirmedFact)
        .filter(
            ConfirmedFact.user_id == user_id,
            ConfirmedFact.category == declaration.category,
            ConfirmedFact.declared_by == "user",
            ConfirmedFact.is_active == True,  # noqa: E712
            ConfirmedFact.content == content,
        )
        .order_by(ConfirmedFact.created_at.desc())
        .first()
    )
    if existing:
        return existing
    fact = ConfirmedFact(
        user_id=user_id,
        category=declaration.category,
        content=content,
        declared_by="user",
        is_active=True,
    )
    db.add(fact)
    db.commit()
    db.refresh(fact)
    return fact

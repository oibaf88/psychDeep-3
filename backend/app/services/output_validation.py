"""Deterministic validation of Agent 1's conversational output.

The LLM boundary in AGENTS.md says the model must not calculate alert/risk
levels, invent emergency resources, prescribe as an authority, or suggest
the excluded pain/cold techniques. Prompting asks for that; this module
*checks* it on every reply before the patient sees it.

Every rule is derived from content the server already owns, not from new
clinical thresholds:

- ``risk_level_claim``: the reply states an alert/risk level or that there
  is "no risk". Only the deterministic risk engine decides levels, and the
  product never claims "sin riesgo" because no signal was detected.
- ``unapproved_contact``: the reply gives a phone number that is not one of
  the server-owned crisis resources (``app/content/safety_resources``).
- ``dosage_instruction``: the reply gives a quantity of a substance
  (mg, ml, gramos, gotas). The model must not prescribe or dose.
- ``forbidden_technique``: the reply suggests one of ``FORBIDDEN_TECHNIQUES``.

A reply that breaks a rule is not repaired or partially shown: the caller
replaces it with deterministic, server-owned support and logs the event
(rule codes only, never the patient's or the model's text).

Agent 3, the professional copilot, gets a narrower rule set
(``validate_copilot_output``). A clinician legitimately reads the engine's
alert level and patient-reported quantities in the dossier, so stated
levels and quantities are not blocked there. What stays blocked for every
audience is what the LLM boundary forbids outright: a "no risk" claim,
an invented contact number and an excluded technique.

This does not change the risk engine, alert levels or crisis rules. It
can only withhold model text; it never lowers or raises an alert.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.content.safety_resources import FORBIDDEN_TECHNIQUES, NATIONAL_CRISIS_RESOURCES, crisis_resources

VALIDATOR_VERSION = "agent1-output-validation-v1"
COPILOT_VALIDATOR_VERSION = "copilot-output-validation-v1"

AUDIT_ACTION = "llm_output_blocked"


def _normalise(text: str) -> str:
    """Lower-case and strip accents so "Ningún" and "ningun" match alike."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


_RISK_LEVEL_PATTERNS = [
    re.compile(p)
    for p in (
        r"\bnivel(?:es)? de (?:alerta|riesgo)\b",
        r"\b(?:alerta|riesgo) (?:de )?nivel\s*\d",
        r"\bnivel\s*[0-4]\s*(?:de|/)\s*(?:alerta|riesgo|4)\b",
        r"\b(?:sin|no hay|no tienes|no existe|no presentas|ningun|cero) (?:ningun )?riesgo\b",
        r"\bno (?:estas|te encuentras) en (?:situacion de )?riesgo\b",
        r"\btu riesgo (?:es|esta|parece)\b",
        r"\briesgo (?:es )?(?:bajo|alto|moderado|nulo|minimo|cero|elevado)\b",
        r"\balert_level\b",
    )
]

# Copilot: only the "no risk" claim, in second or third person. Stated
# levels are allowed because the clinician reads the engine's level anyway.
_NO_RISK_PATTERNS = [
    re.compile(p)
    for p in (
        r"\b(?:sin|no hay|no tienes?|no existe|no presentas?|ningun|cero) (?:ningun )?riesgo\b",
        r"\bno (?:estas?|te encuentras|se encuentra) en (?:situacion de )?riesgo\b",
        r"\briesgo (?:es )?(?:nulo|cero)\b",
    )
]

_DOSAGE_PATTERN = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?(?:mg|miligramos?|ml|mililitros?|cc|gotas?|gramos?|gr)\b"
)

_EXTRA_FORBIDDEN_PATTERNS = [
    re.compile(p)
    for p in (
        r"\bcubitos? de hielo\b",
        r"\bhielo (?:en|sobre|contra) (?:la|tu|el|tus) (?:cara|piel|mano|manos|muneca|cuello)\b",
        r"\bagua (?:helada|muy fria)\b",
        r"\bgomas? elasticas?\b",
        r"\bgoma en la muneca\b",
    )
]

# A phone-like token: 3 to 15 digits, optionally separated by spaces, dots or
# hyphens, optionally with a leading "+". Short three-digit tokens only count
# when the reply is pointing the person to call/contact that number, so that
# "4-7-8" breathing or "10 minutos" are not read as phone numbers.
_PHONE_TOKEN = re.compile(r"(?<![\d,.])\+?\d(?:[ .-]?\d){2,14}(?![\d,])")
_CONTACT_CUE = re.compile(r"\b(?:llama|llamar|llames|llamando|telefono|tlf|tel|linea|marca|marcar|contacta|contactar|numero|whatsapp|sms)\b")


def _approved_numbers() -> set[str]:
    numbers: set[str] = set()
    for item in [*NATIONAL_CRISIS_RESOURCES, *crisis_resources()]:
        digits = re.sub(r"\D", "", str(item.get("contact", "")))
        if digits and digits == str(item.get("contact", "")).replace(" ", ""):
            numbers.add(digits)
    return numbers


@dataclass(frozen=True)
class OutputValidation:
    violations: list[str] = field(default_factory=list)
    validator_version: str = VALIDATOR_VERSION

    @property
    def blocked(self) -> bool:
        return bool(self.violations)

    def audit_extra(self, **context) -> dict:
        """Audit payload: rule codes and context only, never message text."""
        return {"validator_version": self.validator_version, "violations": list(self.violations), **context}


def _unapproved_contact(norm: str) -> bool:
    approved = _approved_numbers()
    for match in _PHONE_TOKEN.finditer(norm):
        digits = re.sub(r"\D", "", match.group(0))
        if digits in approved:
            continue
        if len(digits) >= 9:
            return True
        window = norm[max(0, match.start() - 30): match.start()]
        if len(digits) in (3, 4, 5, 6) and _CONTACT_CUE.search(window):
            return True
    return False


def _forbidden_technique(norm: str) -> bool:
    forbidden = [_normalise(t) for t in FORBIDDEN_TECHNIQUES]
    return any(t in norm for t in forbidden) or any(p.search(norm) for p in _EXTRA_FORBIDDEN_PATTERNS)


def validate_agent1_output(text: str) -> OutputValidation:
    norm = _normalise(text)
    if not norm.strip():
        return OutputValidation()

    violations: list[str] = []

    if any(p.search(norm) for p in _RISK_LEVEL_PATTERNS):
        violations.append("risk_level_claim")

    if _unapproved_contact(norm):
        violations.append("unapproved_contact")

    if _DOSAGE_PATTERN.search(norm):
        violations.append("dosage_instruction")

    if _forbidden_technique(norm):
        violations.append("forbidden_technique")

    return OutputValidation(violations=violations)


def validate_copilot_output(text: str) -> OutputValidation:
    """Agent 3 (professional copilot) rules: no-risk claims, invented
    contacts and excluded techniques. Levels and quantities read from the
    dossier are allowed for a clinician and are not checked here."""
    norm = _normalise(text)
    if not norm.strip():
        return OutputValidation(validator_version=COPILOT_VALIDATOR_VERSION)

    violations: list[str] = []

    if any(p.search(norm) for p in _NO_RISK_PATTERNS):
        violations.append("no_risk_claim")

    if _unapproved_contact(norm):
        violations.append("unapproved_contact")

    if _forbidden_technique(norm):
        violations.append("forbidden_technique")

    return OutputValidation(violations=violations, validator_version=COPILOT_VALIDATOR_VERSION)

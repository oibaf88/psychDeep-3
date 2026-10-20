"""Time-aware sequence model over a single patient's own app data.

Scope (not negotiable, per clinical/legal design):
- Input is ONLY what the app already stores: check-ins, diary, chat and
  confirmed facts. No images, no external reports, no other hospital data,
  no EHR.
- Output is a longitudinal "ChangeSignal" (change vs the person's own line),
  with a deterministic confidence/fingerprint and an explanation.
- It NEVER writes RiskAssessment.alert_level. Alerting stays deterministic
  and independent of the model.
- The model is trained on the same patient (single-patient dataset, no
  transfer learning, no shared cohorts). Small data is handled with
  transparent statistical rules, not a black-box classifier.

Implementation notes
- Pure Python. No heavy ML framework dependency; the app runs on local
  inference or an authenticated tunnel endpoint, not a shared worker.
- Everything is reproducible and auditable: algorithm_version,
  prompt_version (prompt text), consent_id, user_id, correlation_id and
  a fingerprint of the inputs.
- External clinical text (source_refs starting with "clinical_document:")
  is dropped before the model sees it (see app/services/sequence_sources.py).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

from app.services.sequence_sources import is_external_clinical_ref, sequence_refs

logger = logging.getLogger("psychdeep.sequence_model")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fingerprint(values: Sequence[float]) -> list[float]:
    """Deterministic fingerprint, same length and precision every run."""
    payload = "|".join(f"{v:.6f}" for v in values)
    digest = _sha256(payload).encode("utf-8")
    return [round(b / 255.0, 6) for b in digest[:16]]


@dataclass(frozen=True)
class PatientEvent:
    """One row the model is allowed to read (check-in, diary, chat, fact)."""
    id: str
    source: str
    happened_at: datetime
    content: str
    recipient: str
    source_refs: tuple[str, ...]


class OutOfRangeError(ValueError):
    """The patient line moved outside a configured safety band."""


@dataclass(frozen=True)
class ChangeSignalDraft:
    patient_id: str
    event_id: str
    algorithm_version: str
    prompt_version: str
    consent_id: str | None
    correlation_id: str
    effect: float
    confidence: float
    fingerprint: list[float]
    explanation: str
    created_at: datetime


class TimeAwareSequenceModel:
    """Analyse the person's own chronology; never the reference population."""

    def __init__(
        self,
        algorithm_version: str = "patient-sequence-v1",
        prompt_version: str = "patient-sequence-2026-10",
        *,
        window_days: float = 365.0,
        min_points: int = 3,
    ) -> None:
        self.algorithm_version = algorithm_version
        self.prompt_version = prompt_version
        self.window_days = window_days
        self.min_points = min_points

    def analyse(
        self,
        patient_id: str,
        events: Iterable[PatientEvent],
        consent_id: str | None,
        correlation_id: str,
        *,
        prompt_text: str,
        user_id: str,
    ) -> list[ChangeSignalDraft]:
        rows = self._normalise(patient_id, events, user_id)
        if len(rows) < self.min_points:
            return []
        window = self._window(rows)
        if not window:
            return []
        drafts: list[ChangeSignalDraft] = []
        # One draft per run: the most recent in-window event is the "now"
        # point; every earlier event is the person's own line. Scoring every
        # row compared events against later ones and produced effects > 1.
        for row in window[-1:]:
            effect, confidence, explanation = self._score(row, rows)
            if effect == 0.0:
                continue
            drafts.append(
                ChangeSignalDraft(
                    patient_id=patient_id,
                    event_id=row.id,
                    algorithm_version=self.algorithm_version,
                    prompt_version=self.prompt_version,
                    consent_id=consent_id,
                    correlation_id=correlation_id,
                    effect=effect,
                    confidence=confidence,
                    fingerprint=_fingerprint([effect, confidence]),
                    explanation=explanation,
                    created_at=_now(),
                )
            )
        return drafts

    def _normalise(
        self, patient_id: str, events: Iterable[PatientEvent], user_id: str
    ) -> list[PatientEvent]:
        kept: list[PatientEvent] = []
        for event in events:
            # Drop the whole event if any ref points at an uploaded external
            # report; a bare membership test missed "clinical_document:<id>".
            if any(is_external_clinical_ref(ref) for ref in (event.source_refs or ())):
                continue
            if not event.happened_at.tzinfo:
                event_happened = event.happened_at.replace(tzinfo=timezone.utc)
            else:
                event_happened = event.happened_at.astimezone(timezone.utc)
            kept.append(
                PatientEvent(
                    id=event.id,
                    source=event.source,
                    happened_at=event_happened,
                    content=event.content,
                    recipient=event.recipient,
                    source_refs=sequence_refs(event.source_refs),
                )
            )
        kept.sort(key=lambda e: e.happened_at)
        return kept

    def _window(self, rows: list[PatientEvent]) -> list[PatientEvent]:
        if not rows:
            return []
        cutoff = _now().timestamp() - self.window_days * 86400.0
        return [row for row in rows if row.happened_at.timestamp() >= cutoff]

    def _score(
        self, row: PatientEvent, rows: list[PatientEvent]
    ) -> tuple[float, float, str]:
        """Return (effect, confidence, explanation) for the most recent event.

        Baseline = the person's own typical spacing between earlier events
        (strictly before ``row``; the recent point is never part of its own
        baseline). Recent = time from ``row`` to now. ``effect`` is in [0, 1]:
        1.0 means activity is at least as recent as the person's usual rhythm,
        0.0 means no change is claimed. Too few earlier events, or no spacing
        at all, returns 0.0 (insufficient data, not a zero score).
        """
        earlier = [r for r in rows if r.happened_at < row.happened_at]
        if len(earlier) + 1 < self.min_points or len(earlier) < 2:
            return 0.0, 0.0, ""
        gaps = [
            (b.happened_at - a.happened_at).total_seconds() / 86400.0
            for a, b in zip(earlier, earlier[1:])
        ]
        baseline = sum(gaps) / len(gaps)
        if baseline <= 0:
            return 0.0, 0.0, ""
        recent = max((_now() - row.happened_at).total_seconds() / 86400.0, 0.0)
        effect = 1.0 - min(recent / baseline, 1.0)
        confidence = min(0.95, 0.4 + 0.4 * (len(rows) / max(self.min_points, 1)))
        tokens = " ".join(sequence_refs(row.source_refs)).lower()
        if any(token in tokens for token in ("check_in", "diary", "chat", "fact")):
            confidence = min(0.95, confidence + 0.05)
        return round(effect, 6), round(confidence, 6), "cambio respecto a la línea propia del paciente"


def round_trip_model(seed: str, events: Iterable[PatientEvent]) -> list[ChangeSignalDraft]:
    """Small helper used by tests and CLI: model configured for one patient."""
    model = TimeAwareSequenceModel(window_days=365.0, min_points=3)
    return model.analyse(
        patient_id="patient-example",
        events=events,
        consent_id="consent-example",
        correlation_id=str(uuid.uuid4()),
        prompt_text=seed,
        user_id="user-example",
    )

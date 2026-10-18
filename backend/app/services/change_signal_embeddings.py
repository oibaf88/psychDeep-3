"""Fail-closed embeddings on ChangeSignal. Retrieval only; never alert_level."""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import User
from app.models_vnext import ChangeSignal, ChangeSignalEmbedding
from app.services.consent import LINGUISTIC_ANALYSIS, is_granted

logger = logging.getLogger("psychapp.change_signal_embeddings")

ALGORITHM_VERSION = "cse-deterministic-v1"
PROVIDER = "local_deterministic"
EMBEDDING_MODEL = "change-signal-fingerprint-v1"
PURPOSE = "linguistic_analysis"

# Crisis/chemsex language must not become a retrieval vector on the baseline path.
_BLOCKED_FEATURE_TOKENS = (
    "crisis",
    "chemsex",
    "ghb",
    "gbl",
    "restraint",
    "suicid",
    "self_harm",
    "self-harm",
)


def current_consent_id(db: Session, user_id, purpose: str = LINGUISTIC_ANALYSIS):
    from app.models import Consent

    row = (
        db.query(Consent)
        .filter(Consent.user_id == user_id, Consent.consent_type == purpose, Consent.revoked_at.is_(None))
        .order_by(Consent.granted_at.desc(), Consent.id.desc())
        .first()
    )
    if row and row.granted:
        return row.id
    return None


def _blocked_feature(feature: str) -> bool:
    name = (feature or "").lower()
    return any(token in name for token in _BLOCKED_FEATURE_TOKENS)


def _fingerprint(signal: ChangeSignal) -> list[float]:
    payload = f"{signal.feature}|{signal.change_value}|{signal.band}|{signal.algorithm_version}"
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return [round(b / 255.0, 6) for b in digest[:16]]


def embed_change_signals(db: Session, user_id, signals: list[ChangeSignal] | None = None) -> int:
    """Write embeddings for new ChangeSignals. No-op without grant / active user.

    Does not read or write RiskAssessment.alert_level.
    """
    user = db.get(User, user_id)
    if user is None or not getattr(user, "is_active", True):
        return 0
    if not is_granted(db, user_id, LINGUISTIC_ANALYSIS):
        return 0
    consent_id = current_consent_id(db, user_id, LINGUISTIC_ANALYSIS)
    if consent_id is None:
        return 0

    if signals is None:
        signals = (
            db.query(ChangeSignal)
            .filter(ChangeSignal.user_id == user_id)
            .order_by(ChangeSignal.created_at.desc())
            .limit(50)
            .all()
        )
    written = 0
    now = datetime.now(timezone.utc)
    for signal in signals:
        if signal.user_id != user_id:
            continue
        if _blocked_feature(signal.feature):
            continue
        exists = (
            db.query(ChangeSignalEmbedding)
            .filter(ChangeSignalEmbedding.change_signal_id == signal.id)
            .first()
        )
        if exists is not None:
            continue
        row = ChangeSignalEmbedding(
            id=uuid.uuid4(),
            user_id=user_id,
            change_signal_id=signal.id,
            consent_id=consent_id,
            purpose=PURPOSE,
            embedding=_fingerprint(signal),
            provider=PROVIDER,
            embedding_model=EMBEDDING_MODEL,
            algorithm_version=ALGORITHM_VERSION,
            created_at=now,
        )
        db.add(row)
        written += 1
    if written:
        db.commit()
    return written

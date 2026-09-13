"""Granular, revocable consent checks used by vNext processing paths."""
from sqlalchemy.orm import Session

from app.models import Consent

CORE_PROCESSING = "data_processing"
LINGUISTIC_ANALYSIS = "linguistic_analysis"
PROFESSIONAL_SHARING = "professional_sharing"
CRISIS_COMMUNICATIONS = "crisis_sms"
RESEARCH_MODEL_IMPROVEMENT = "research"

VALID_PURPOSES = {
    CORE_PROCESSING,
    LINGUISTIC_ANALYSIS,
    PROFESSIONAL_SHARING,
    CRISIS_COMMUNICATIONS,
    RESEARCH_MODEL_IMPROVEMENT,
}


def is_granted(db: Session, user_id, purpose: str) -> bool:
    """Return the latest effective grant for one purpose.

    Consent is append-only/versioned. A revoked row is historical; the newest
    non-revoked row is authoritative. `granted=False` explicitly denies the
    purpose and stops future processing without rewriting earlier records.
    """
    row = (
        db.query(Consent)
        .filter(Consent.user_id == user_id, Consent.consent_type == purpose, Consent.revoked_at.is_(None))
        .order_by(Consent.granted_at.desc(), Consent.id.desc())
        .first()
    )
    return bool(row and row.granted)

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Consent, User
from app.schemas import ConsentIn, ConsentOut
from app.security import get_current_user
from app.services import audit
from app.services.consent import VALID_PURPOSES

router = APIRouter(prefix="/api/v1/consents", tags=["consents"])

VALID_CONSENT_TYPES = VALID_PURPOSES


@router.get("", response_model=list[ConsentOut])
def list_consents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Consent).filter(Consent.user_id == user.id).order_by(Consent.granted_at.desc()).all()


@router.post("", response_model=ConsentOut, status_code=201)
def set_consent(payload: ConsentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Append a granular purpose grant/revocation without rewriting history."""
    if payload.consent_type not in VALID_CONSENT_TYPES:
        raise HTTPException(status_code=400, detail=f"consent_type must be one of {sorted(VALID_CONSENT_TYPES)}")
    consent_type = payload.consent_type

    previous = (
        db.query(Consent)
        .filter(Consent.user_id == user.id, Consent.consent_type == consent_type, Consent.revoked_at.is_(None))
        .all()
    )
    for row in previous:
        row.revoked_at = datetime.utcnow()

    consent = Consent(user_id=user.id, consent_type=consent_type, granted=payload.granted)
    db.add(consent)
    db.commit()
    db.refresh(consent)

    audit.log(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="consent_set",
        entity_type="consent",
        entity_id=consent.id,
        extra={"consent_type": consent_type, "granted": payload.granted},
    )
    return consent

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Consent, User
from app.models_vnext import PatientClinicalDocument
from app.schemas import ConsentIn, ConsentOut
from app.security import get_current_user
from app.services import audit
from app.services.consent import (
    CLINICAL_DOCUMENT_ANALYSIS,
    LINGUISTIC_ANALYSIS,
    NOT_OFFERED_YET,
    VALID_PURPOSES,
    is_granted,
)
from app.services.memory_pipeline import enqueue_memory_job

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
    if payload.consent_type in NOT_OFFERED_YET:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{payload.consent_type} is a distinct purpose and is not collected until "
                "versioned volume ingest exists. data_processing does not cover it."
            ),
        )
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
    db.flush()

    if consent_type in {LINGUISTIC_ANALYSIS, CLINICAL_DOCUMENT_ANALYSIS}:
        document_consent_active = is_granted(db, user.id, CLINICAL_DOCUMENT_ANALYSIS)
        linguistic_consent_active = is_granted(db, user.id, LINGUISTIC_ANALYSIS)

        if not document_consent_active or not linguistic_consent_active:
            db.query(PatientClinicalDocument).filter(
                PatientClinicalDocument.user_id == user.id,
                PatientClinicalDocument.extraction_status == "text_extracted",
            ).update({
                PatientClinicalDocument.analysis_status: "consent_revoked",
                PatientClinicalDocument.error_category: "consent_revoked",
            }, synchronize_session=False)
        else:
            db.query(PatientClinicalDocument).filter(
                PatientClinicalDocument.user_id == user.id,
                PatientClinicalDocument.extraction_status == "text_extracted",
            ).update({
                PatientClinicalDocument.analysis_status: "queued",
                PatientClinicalDocument.error_category: None,
            }, synchronize_session=False)

        if linguistic_consent_active:
            enqueue_memory_job(
                db,
                user_id=user.id,
                job_type="longitudinal_analysis",
                source_table="patient_model",
                source_id=user.id,
                idempotency_key=f"patient-model:consent:{consent.id}",
            )

    audit.log(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="consent_set",
        entity_type="consent",
        entity_id=consent.id,
        extra={"consent_type": consent_type, "granted": payload.granted},
    )
    db.refresh(consent)
    return consent

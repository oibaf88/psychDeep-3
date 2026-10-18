"""Art. 15/20 access+portability and a non-destructive art. 17 request.

Ley 41/2002 art. 17 may require keeping clinical history. Even if PsychDeep is
not (yet) a healthcare provider, risk/audit rows are not hard-deleted here.
New processing stops: consents revoked, account deactivated, JWTs invalidated.
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from app.models import (
    CheckIn,
    ConfirmedFact,
    Consent,
    DiaryEntry,
    PatientProfessionalAssignment,
    RiskAssessment,
    SafetyPlan,
    User,
)
from app.services import audit
from app.services.consent import (
    CLINICAL_DOCUMENT_ANALYSIS,
    CORE_PROCESSING,
    LINGUISTIC_ANALYSIS,
    PROFESSIONAL_SHARING,
)

# Purposes that actually drive processing. research/crisis_sms are not offered.
OFFERED_PURPOSES = {
    CORE_PROCESSING,
    LINGUISTIC_ANALYSIS,
    CLINICAL_DOCUMENT_ANALYSIS,
    PROFESSIONAL_SHARING,
}

EXPORT_SCHEMA = "psychdeep-data-export-v1"

RETENTION_NOTE = (
    "El histórico clínico (diario, check-ins, hechos, evaluaciones de riesgo) "
    "no se borra en este paso. Si el tratamiento llega a ser historia clínica, "
    "Ley 41/2002 art. 17 puede exigir conservación (mín. 5 años desde la última "
    "atención). Art. 17.3 RGPD (deber legal, reclamaciones, salud pública). "
    "Sí se detiene el tratamiento futuro: consentimientos revocados, cuenta "
    "desactivada, sesiones invalidadas, vinculaciones terminadas."
)


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def build_export(db: Session, user: User) -> dict:
    """Patient-provided data (art. 20) plus access copy of derived safety (art. 15)."""
    consents = (
        db.query(Consent).filter(Consent.user_id == user.id).order_by(Consent.granted_at.asc()).all()
    )
    checkins = db.query(CheckIn).filter(CheckIn.user_id == user.id).order_by(CheckIn.created_at.asc()).all()
    diary = db.query(DiaryEntry).filter(DiaryEntry.user_id == user.id).order_by(DiaryEntry.created_at.asc()).all()
    facts = db.query(ConfirmedFact).filter(ConfirmedFact.user_id == user.id).order_by(ConfirmedFact.created_at.asc()).all()
    risks = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.user_id == user.id)
        .order_by(RiskAssessment.calculated_at.asc())
        .all()
    )
    assignments = (
        db.query(PatientProfessionalAssignment)
        .filter(PatientProfessionalAssignment.patient_id == user.id)
        .order_by(PatientProfessionalAssignment.requested_at.asc())
        .all()
    )
    plan = db.query(SafetyPlan).filter(SafetyPlan.user_id == user.id).first()

    return {
        "schema": EXPORT_SCHEMA,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "legal": {
            "gdpr_articles": ["15", "20"],
            "portability_covers": ["account", "consents", "check_ins", "diary_entries", "confirmed_facts", "safety_plan"],
            "access_also_includes": ["risk_assessments", "assignments"],
            "retention_note": RETENTION_NOTE,
        },
        "account": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "locale": user.locale,
            "role": user.role,
            "created_at": _iso(user.created_at),
        },
        "consents": [
            {
                "id": str(c.id),
                "consent_type": c.consent_type,
                "granted": c.granted,
                "version": c.version,
                "granted_at": _iso(c.granted_at),
                "revoked_at": _iso(c.revoked_at),
            }
            for c in consents
        ],
        "check_ins": [
            {
                "id": str(row.id),
                "mood": row.mood,
                "craving": row.craving,
                "sleep_hours": row.sleep_hours,
                "self_efficacy": row.self_efficacy,
                "notes": row.notes,
                "created_at": _iso(row.created_at),
            }
            for row in checkins
        ],
        "diary_entries": [
            {"id": str(row.id), "content": row.content, "created_at": _iso(row.created_at)} for row in diary
        ],
        "confirmed_facts": [
            {
                "id": str(row.id),
                "category": row.category,
                "content": row.content,
                "declared_by": row.declared_by,
                "is_active": row.is_active,
                "created_at": _iso(row.created_at),
            }
            for row in facts
        ],
        "safety_plan": None
        if plan is None
        else {
            "warning_signs": plan.warning_signs,
            "coping_strategies": plan.coping_strategies,
            "social_supports": plan.social_supports,
            "professional_contacts": plan.professional_contacts,
            "safe_environment": plan.safe_environment,
            "reasons_to_live": plan.reasons_to_live,
            "updated_at": _iso(plan.updated_at),
        },
        "risk_assessments": [
            {
                "id": str(row.id),
                "alert_level": row.alert_level,
                "triggering_rules": row.triggering_rules,
                "assessment_reason": row.assessment_reason,
                "model_version": row.model_version,
                "calculated_at": _iso(row.calculated_at),
            }
            for row in risks
        ],
        "assignments": [
            {
                "id": str(row.id),
                "professional_id": str(row.professional_id),
                "status": row.status,
                "requested_at": _iso(row.requested_at),
            }
            for row in assignments
        ],
    }


def apply_erasure_request(db: Session, user: User) -> dict:
    """Stop future processing without destroying the clinical record."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for purpose in OFFERED_PURPOSES:
        open_rows = (
            db.query(Consent)
            .filter(Consent.user_id == user.id, Consent.consent_type == purpose, Consent.revoked_at.is_(None))
            .all()
        )
        for row in open_rows:
            row.revoked_at = now
        db.add(Consent(user_id=user.id, consent_type=purpose, granted=False))

    for assignment in (
        db.query(PatientProfessionalAssignment)
        .filter(
            PatientProfessionalAssignment.patient_id == user.id,
            PatientProfessionalAssignment.status.in_(["pending", "active", "paused"]),
        )
        .all()
    ):
        assignment.status = "ended"
        assignment.updated_at = now

    user.is_active = False
    user.auth_version = (user.auth_version or 1) + 1
    user.updated_at = now
    db.commit()

    audit.log(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="erasure_request",
        entity_type="user",
        entity_id=user.id,
        extra={"hard_delete": False, "clinical_rows_retained": True},
    )
    return {
        "status": "processing_stopped",
        "hard_delete": False,
        "account_active": False,
        "retention_note": RETENTION_NOTE,
        "request_id": str(uuid.uuid4()),
    }

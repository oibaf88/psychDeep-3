"""Clinical memory reads for assigned clinicians. Nobody edits or deletes it."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PatientProfessionalAssignment, User
from app.security import get_current_user, require_professional
from app.services import clinical_memory
from app.utils import utc_iso

router = APIRouter(prefix="/api/v1", tags=["clinical-memory"])

_IMMUTABLE = "La memoria clínica no se modifica ni se borra."
_HIDDEN = "La formulación clínica no se muestra en la cuenta del paciente."


class AnnotationIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    target_type: str = Field(pattern="^(discourse|reading|formulation)$")
    target_id: uuid.UUID


def _assignment(db: Session, patient_id, professional_id, statuses=("active", "paused")) -> bool:
    row = (
        db.query(PatientProfessionalAssignment)
        .filter(
            PatientProfessionalAssignment.patient_id == patient_id,
            PatientProfessionalAssignment.professional_id == professional_id,
            PatientProfessionalAssignment.status.in_(list(statuses)),
        )
        .first()
    )
    return row is not None


def _require_clinical_read(db: Session, professional: User, patient_id: uuid.UUID) -> None:
    if professional.role == "admin_clinical":
        raise HTTPException(status_code=403, detail="admin_clinical no tiene visibilidad clínica de la memoria")
    if professional.role == "therapist" and not _assignment(db, patient_id, professional.id):
        raise HTTPException(status_code=403, detail="No tienes asignación activa/pausada con este paciente")


def _require_active_writer(db: Session, professional: User, patient_id: uuid.UUID) -> None:
    _require_clinical_read(db, professional, patient_id)
    if professional.role == "therapist" and not _assignment(db, patient_id, professional.id, statuses=("active",)):
        raise HTTPException(status_code=403, detail="Se requiere asignación activa para anotar la memoria")


def _iso(value) -> str | None:
    if value is None:
        return None
    return utc_iso(value)


def _view(rows) -> dict:
    formulation = rows["formulation"]
    return {
        "formulation": None
        if formulation is None
        else {
            "id": str(formulation.id),
            "l0": formulation.l0,
            "l1": formulation.l1,
            "l2": formulation.l2,
            "acute_episode": formulation.acute_episode,
            "prompt_version": formulation.prompt_version,
            "created_at": _iso(formulation.created_at),
        },
        "formulation_history": [
            {
                "id": str(row.id),
                "l0": row.l0,
                "acute_episode": row.acute_episode,
                "created_at": _iso(row.created_at),
            }
            for row in rows["formulation_history"]
        ],
        "discourse": [
            {
                "id": str(row.id),
                "channel": row.channel,
                "quote": row.quote,
                "manner": row.manner,
                "spoken_at": _iso(row.spoken_at),
            }
            for row in rows["discourse"]
        ],
        "readings": [
            {
                "id": str(row.id),
                "kind": row.kind,
                "uncertainty": row.uncertainty,
                "hypothesis": row.hypothesis,
                "status": row.status,
                "evidence_refs": row.evidence_refs,
                "created_at": _iso(row.created_at),
            }
            for row in rows["readings"]
        ],
        "notices": [
            {
                "id": str(row.id),
                "reason": row.reason,
                "status": row.status,
                "evidence_refs": row.evidence_refs,
                "created_at": _iso(row.created_at),
                "acknowledged_at": _iso(row.acknowledged_at),
            }
            for row in rows["notices"]
        ],
        "annotations": [
            {
                "id": str(row.id),
                "body": row.body,
                "target_type": row.target_type,
                "target_id": str(row.target_id),
                "created_at": _iso(row.created_at),
            }
            for row in rows["annotations"]
        ],
    }


@router.get("/memory")
def patient_memory_is_hidden(user: User = Depends(get_current_user)):
    raise HTTPException(status_code=403, detail=_HIDDEN)


@router.api_route("/memory/{memory_id}", methods=["PUT", "PATCH", "DELETE"])
def memory_is_immutable(memory_id: uuid.UUID, user: User = Depends(get_current_user)):
    raise HTTPException(status_code=403, detail=_IMMUTABLE)


@router.get("/professional/patients/{patient_id}/memory")
def read_patient_memory(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    professional: User = Depends(require_professional),
):
    _require_clinical_read(db, professional, patient_id)
    return _view(clinical_memory.bundle(db, patient_id))


@router.post("/professional/patients/{patient_id}/memory/annotations", status_code=201)
def annotate_memory(
    patient_id: uuid.UUID,
    payload: AnnotationIn,
    db: Session = Depends(get_db),
    professional: User = Depends(require_professional),
):
    _require_active_writer(db, professional, patient_id)
    try:
        row = clinical_memory.add_annotation(
            db,
            patient_id=patient_id,
            author_id=professional.id,
            body=payload.body,
            target_type=payload.target_type,
            target_id=payload.target_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="No existe esa memoria para este paciente") from None
    except ValueError:
        raise HTTPException(status_code=422, detail="La nota está vacía") from None
    return {"id": str(row.id), "body": row.body, "target_type": row.target_type, "target_id": str(row.target_id)}


@router.post("/professional/patients/{patient_id}/memory/notices/{notice_id}/acknowledge")
def acknowledge_notice(
    patient_id: uuid.UUID,
    notice_id: uuid.UUID,
    db: Session = Depends(get_db),
    professional: User = Depends(require_professional),
):
    _require_active_writer(db, professional, patient_id)
    try:
        notice = clinical_memory.acknowledge_notice(
            db, patient_id=patient_id, notice_id=notice_id, professional_id=professional.id
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="No existe ese aviso") from None
    return {"id": str(notice.id), "status": notice.status}

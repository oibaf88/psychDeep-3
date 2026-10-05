"""Operational assignment reads for roles that manage links, not charts.

``pending`` is a request the patient has not accepted. Everything else
(active, paused, ended, rejected, or a legacy status) is a made assignment:
"hecha". A missing link is ``none``. It is not zero, not healthy, and not
an alert level.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import PatientProfessionalAssignment, User

PENDING_STATUS = "pending"
SUMMARY_PRIORITY = ("pending", "active", "paused", "ended", "rejected")


@dataclass(frozen=True)
class AssignmentLink:
    id: uuid.UUID
    professional_id: uuid.UUID
    professional_display_name: str | None
    professional_email: str | None
    status: str
    requested_at: datetime
    updated_at: datetime | None


def is_pending(status: str) -> bool:
    return status == PENDING_STATUS


def is_done(status: str) -> bool:
    return status != PENDING_STATUS


def summary_status(statuses: list[str]) -> str:
    """One label for a patient who may have several links.

    Pending wins so a request still waiting is not hidden behind an older
    active link. Callers that need both groups must read the link list.
    """
    present = set(statuses)
    if not present:
        return "none"
    for status in SUMMARY_PRIORITY:
        if status in present:
            return status
    return next(iter(present))


def links_by_patient(db: Session, patient_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[AssignmentLink]]:
    if not patient_ids:
        return {}
    rows = (
        db.query(PatientProfessionalAssignment)
        .filter(PatientProfessionalAssignment.patient_id.in_(patient_ids))
        .order_by(PatientProfessionalAssignment.requested_at.desc())
        .all()
    )
    professional_ids = {row.professional_id for row in rows}
    professionals = (
        {user.id: user for user in db.query(User).filter(User.id.in_(professional_ids)).all()}
        if professional_ids
        else {}
    )
    grouped: dict[uuid.UUID, list[AssignmentLink]] = {}
    for row in rows:
        professional = professionals.get(row.professional_id)
        grouped.setdefault(row.patient_id, []).append(
            AssignmentLink(
                id=row.id,
                professional_id=row.professional_id,
                professional_display_name=professional.display_name if professional else None,
                professional_email=professional.email if professional else None,
                status=row.status,
                requested_at=row.requested_at,
                updated_at=row.updated_at,
            )
        )
    return grouped

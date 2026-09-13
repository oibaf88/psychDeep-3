from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CheckIn, User
from app.schemas import CheckInIn, CheckInOut
from app.security import require_patient
from app.services import audit, risk_engine
from app.services.canonical_data import record_checkin

router = APIRouter(prefix="/api/v1/checkins", tags=["checkins"])


@router.post("", response_model=CheckInOut, status_code=201)
def create_checkin(payload: CheckInIn, db: Session = Depends(get_db), user: User = Depends(require_patient)):
    checkin = CheckIn(user_id=user.id, **payload.model_dump())
    db.add(checkin)
    db.commit()
    db.refresh(checkin)

    # Expand-and-migrate compatibility: keep the established row readable and
    # mirror the same self-report into the canonical vNext Observation stream.
    record_checkin(db, checkin)

    audit.log(db, actor_id=user.id, actor_role=user.role, action="checkin_created", entity_type="check_in", entity_id=checkin.id)

    # Safety remains deterministic and independent of the model deployment.
    risk_engine.run_and_persist(db, user.id)

    return checkin


@router.get("", response_model=list[CheckInOut])
def list_checkins(db: Session = Depends(get_db), user: User = Depends(require_patient), limit: int = 30):
    return (
        db.query(CheckIn)
        .filter(CheckIn.user_id == user.id)
        .order_by(CheckIn.created_at.desc())
        .limit(limit)
        .all()
    )

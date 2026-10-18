"""GDPR arts. 15/17/20 endpoints for the signed-in patient."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import require_patient
from app.services import data_rights

router = APIRouter(prefix="/api/v1/me", tags=["data-rights"])


@router.get("/data-export")
def export_my_data(db: Session = Depends(get_db), user: User = Depends(require_patient)):
    return data_rights.build_export(db, user)


@router.post("/erasure-request")
def request_erasure(db: Session = Depends(get_db), user: User = Depends(require_patient)):
    return data_rights.apply_erasure_request(db, user)

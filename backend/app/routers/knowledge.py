from datetime import date, datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models_vnext import KnowledgeItem
from app.schemas import KnowledgeItemDraftIn, KnowledgeItemOut
from app.security import require_admin, require_professional

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.get("", response_model=list[KnowledgeItemOut])
def list_registry(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    status_filter: str | None = Query(default=None, alias="status"),
):
    query = db.query(KnowledgeItem)
    if status_filter is not None:
        if status_filter not in {"draft", "active", "retired"}:
            raise HTTPException(status_code=400, detail="Unsupported knowledge status")
        query = query.filter(KnowledgeItem.status == status_filter)
    return query.order_by(KnowledgeItem.created_at.desc()).all()


@router.get("/retrieve", response_model=list[KnowledgeItemOut])
def retrieve_approved(
    population: str = Query(min_length=1, max_length=96),
    objective: str = Query(min_length=1, max_length=128),
    topic: str = Query(min_length=1, max_length=96),
    locale: str = Query(default="es-ES", min_length=2, max_length=16),
    contraindication: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_professional),
):
    """Targeted registry lookup for future RAG use; no LLM call occurs here."""
    blocked = {value.strip().lower() for value in (contraindication or []) if value.strip()}
    rows = (
        db.query(KnowledgeItem)
        .filter(
            KnowledgeItem.status == "active",
            KnowledgeItem.population == population.strip(),
            KnowledgeItem.objective == objective.strip(),
            KnowledgeItem.topic == topic.strip(),
            KnowledgeItem.locale == locale.strip(),
            or_(KnowledgeItem.review_due.is_(None), KnowledgeItem.review_due >= date.today()),
        )
        .order_by(KnowledgeItem.created_at.desc())
        .all()
    )
    return [
        row
        for row in rows
        if not blocked.intersection({value.lower() for value in (row.contraindications or [])})
    ]


@router.post("", response_model=KnowledgeItemOut, status_code=status.HTTP_201_CREATED)
def create_draft(
    payload: KnowledgeItemDraftIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if payload.review_due <= date.today():
        raise HTTPException(status_code=422, detail="review_due must be in the future")
    item = KnowledgeItem(**payload.model_dump(), status="draft")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/approve", response_model=KnowledgeItemOut)
def approve_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = db.get(KnowledgeItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    if item.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft items can be approved")
    if not item.source_ref.strip() or not item.evidence_level.strip() or item.review_due is None:
        raise HTTPException(status_code=422, detail="Source, evidence level and review date are required")
    if item.review_due <= date.today():
        raise HTTPException(status_code=422, detail="review_due must be in the future")

    predecessors = (
        db.query(KnowledgeItem)
        .filter(
            KnowledgeItem.status == "active",
            KnowledgeItem.topic == item.topic,
            KnowledgeItem.population == item.population,
            KnowledgeItem.objective == item.objective,
            KnowledgeItem.locale == item.locale,
            KnowledgeItem.id != item.id,
        )
        .all()
    )
    for predecessor in predecessors:
        predecessor.status = "retired"

    item.status = "active"
    item.approved_by = admin.email
    item.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{item_id}/retire", response_model=KnowledgeItemOut)
def retire_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    item = db.get(KnowledgeItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    item.status = "retired"
    db.commit()
    db.refresh(item)
    return item

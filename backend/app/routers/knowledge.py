from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import KnowledgeItem, User
from app.schemas import KnowledgeItemIn, KnowledgeItemOut
from app.security import get_current_user, require_admin

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

@router.get("", response_model=list[KnowledgeItemOut])
def list_active_knowledge(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Return all active knowledge items for RAG context."""
    return db.query(KnowledgeItem).filter(KnowledgeItem.is_active == True).all()

@router.post("", response_model=KnowledgeItemOut, status_code=201)
def create_knowledge_item(
    payload: KnowledgeItemIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create a new curated knowledge item (Admin only)."""
    item = KnowledgeItem(
        population_target=payload.population_target,
        clinical_objective=payload.clinical_objective,
        content=payload.content,
        evidence_level=payload.evidence_level,
        contraindications=payload.contraindications,
        version=payload.version,
        is_active=payload.is_active,
        reviewed_at=datetime.utcnow(),
        reviewed_by=admin.id
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

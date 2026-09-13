from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatMessage, User
from app.schemas import ChatIn, ChatMessageOut, ChatOut
from app.security import require_patient
from app.services import conversation
from app.services.deterministic_safety_text import materialize_user_declaration

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("", response_model=ChatOut)
def send_message(payload: ChatIn, db: Session = Depends(get_db), user: User = Depends(require_patient)):
    # Safety is evaluated independently of generative availability. Explicit
    # first-person crisis declarations become user-originated facts before any
    # LLM call; the existing deterministic risk engine therefore still sees
    # them when the selected model/tunnel is unavailable or analysis consent
    # has been revoked.
    materialize_user_declaration(db, user.id, payload.message)
    result = conversation.get_reply(db, user, payload.message)
    return ChatOut(**result)


@router.get("/history", response_model=list[ChatMessageOut])
def history(db: Session = Depends(get_db), user: User = Depends(require_patient), limit: int = 50):
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))

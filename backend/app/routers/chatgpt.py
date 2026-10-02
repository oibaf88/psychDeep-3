from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import ChatIn, ChatOut
from app.security import require_patient
from app.services import conversation

router = APIRouter(prefix="/api/v1/chatgpt", tags=["chatgpt"])


@router.post("", response_model=ChatOut)
def send_message(
    payload: ChatIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_patient),
):
    """Run the normal PsychDeep clinical conversation pipeline using OpenAI."""
    result = conversation.get_reply_with_safety(
        db,
        user,
        payload.message,
        provider_override="openai",
    )
    return ChatOut(**result)

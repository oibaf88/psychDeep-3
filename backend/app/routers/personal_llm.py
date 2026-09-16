"""Per-account model settings: all four roles, own row only, no secret reads."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import get_current_user
from app.services import audit, personal_llm

router = APIRouter(prefix="/personal", tags=["personal-llm"])


class PersonalLLMSettingsIn(BaseModel):
    provider: str = Field(pattern="^(anthropic|openai_compatible)$")
    base_url: str = Field(default="", max_length=500)
    chat_model: str = Field(min_length=1, max_length=192)
    analysis_model: str = Field(min_length=1, max_length=192)
    copilot_model: str = Field(default="", max_length=192)
    max_tokens: int = Field(default=4096, ge=256, le=32768)
    timeout_seconds: int = Field(default=120, ge=5, le=5000)
    # None preserves existing, "" revokes, nonempty rotates. Never returned.
    lm_api_key: str | None = Field(default=None, max_length=8192, repr=False)
    cf_client_id: str | None = Field(default=None, max_length=8192, repr=False)
    cf_client_secret: str | None = Field(default=None, max_length=8192, repr=False)


@router.get("")
def read_personal_settings(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return personal_llm.status(db, user.id)


@router.put("")
def update_personal_settings(
    payload: PersonalLLMSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        result = personal_llm.save(db, user.id, payload)
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None
    audit.log(db, actor_id=user.id, actor_role=user.role,
              action="personal_llm_settings_updated", entity_type="llm_user_preferences",
              entity_id=user.id, extra={"provider": payload.provider})
    return result


@router.delete("")
def delete_personal_settings(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    row = db.get(personal_llm.UserLLMPreference, user.id)
    if row is not None:
        db.delete(row)
        db.commit()
    audit.log(db, actor_id=user.id, actor_role=user.role,
              action="personal_llm_settings_deleted", entity_type="llm_user_preferences",
              entity_id=user.id)
    return personal_llm.status(db, user.id)


@router.post("/test")
def test_personal_settings(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Synthetic test only; uses THIS account's stored credentials."""
    try:
        from app.services.llm import build_provider
        provider = build_provider(personal_llm.resolve(db, user.id))
        answer = provider.chat("Responde solo OK.", [{"role": "user", "content": "OK"}], max_tokens=16)
        return {"ok": bool(answer.text.strip()), "detail": "Respuesta recibida." if answer.text.strip() else "Respuesta vacía."}
    except Exception:
        # Do not expose HTTPX errors: proxy responses can echo headers.
        return {"ok": False, "detail": "Conexión o autenticación fallida. Revisa ambas credenciales y el modelo."}

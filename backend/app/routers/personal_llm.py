"""Authenticated account model preferences; Access credentials remain in Render."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import get_current_user
from app.services import audit, local_llm_access, personal_llm
from app.services.llm.base import StructuredAnalysisError

router = APIRouter(prefix="/personal", tags=["personal-llm"])


class PersonalLLMSettingsIn(BaseModel):
    # Reject arbitrary endpoints, Access secrets and the cloudflared token.
    # None preserves ciphertext, an empty string revokes, nonempty rotates.
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(pattern="^(anthropic|openai_compatible)$")
    chat_model: str = Field(min_length=1, max_length=192)
    analysis_model: str = Field(min_length=1, max_length=192)
    copilot_model: str = Field(default="", max_length=192)
    max_tokens: int = Field(default=4096, ge=256, le=32768)
    timeout_seconds: int = Field(default=120, ge=5, le=5000)
    lm_api_key: str | None = Field(default=None, max_length=8192, repr=False)


def _status_for(db: Session, user: User) -> dict:
    state = personal_llm.status(db, user.id)
    state.update(local_llm_access.public_status(user))
    return state


@router.get("")
def read_personal_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _status_for(db, user)


@router.put("")
def update_personal_settings(
    payload: PersonalLLMSettingsIn,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    if payload.provider == "openai_compatible":
        try:
            local_llm_access.assert_can_use_local_llm(user)
        except local_llm_access.LocalLlmAccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
    try:
        personal_llm.save(db, user.id, payload)
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None
    audit.log(db, actor_id=user.id, actor_role=user.role,
              action="personal_llm_settings_updated", entity_type="llm_user_preferences",
              entity_id=user.id, extra={"provider": payload.provider})
    return _status_for(db, user)


@router.delete("")
def delete_personal_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(personal_llm.UserLLMPreference, user.id)
    if row is not None:
        db.delete(row)
        db.commit()
    audit.log(db, actor_id=user.id, actor_role=user.role,
              action="personal_llm_settings_deleted", entity_type="llm_user_preferences",
              entity_id=user.id)
    return _status_for(db, user)


@router.post("/test")
def test_personal_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Send a synthetic prompt using only the current account's saved key."""
    try:
        from app.services.llm import build_provider
        resolved = personal_llm.resolve(db, user.id)
        if resolved.provider == "openai_compatible":
            local_llm_access.assert_can_use_local_llm(user)
        provider = build_provider(resolved)
        answer = provider.chat("Responde solo OK.", [{"role": "user", "content": "OK"}], max_tokens=16)
        return {"ok": bool(answer.text.strip()), "detail": "Respuesta recibida." if answer.text.strip() else "El modelo devolvió una respuesta vacía."}
    except StructuredAnalysisError as exc:
        labels = {
            "http_401": "Autenticación rechazada (HTTP 401). Revisa el Service Token de Cloudflare y tu API key de LM Studio.",
            "http_403": "Acceso denegado (HTTP 403) por Cloudflare o LM Studio. Revisa ambas políticas; el código no identifica qué capa lo devolvió.",
            "http_404": "Ruta o modelo no encontrado (HTTP 404). Revisa el ID real del modelo en LM Studio.",
            "http_400": "Solicitud rechazada (HTTP 400). Revisa el modelo y los parámetros admitidos.",
            "local_endpoint_unreachable": "No se alcanza el servidor. Comprueba cloudflared y LM Studio.",
            "local_endpoint_timeout": "Tiempo agotado. Comprueba si el modelo está cargado.",
            "non_json_response": "Respuesta no JSON. Revisa las credenciales del gateway y la ruta del servidor.",
        }
        return {"ok": False, "detail": labels.get(exc.error_code, "El proveedor ha rechazado la prueba. Revisa los registros seguros del backend.")}
    except local_llm_access.LocalLlmAccessDenied as exc:
        return {"ok": False, "detail": str(exc)}
    except (ValueError, RuntimeError):
        return {"ok": False, "detail": "La configuración de tu cuenta o del gateway está incompleta. Revisa tu API key o contacta con la administración."}
    except Exception:
        # Never relay exception text: proxies can echo headers and credentials.
        return {"ok": False, "detail": "Error de conexión no identificado. Revisa los registros seguros del backend."}

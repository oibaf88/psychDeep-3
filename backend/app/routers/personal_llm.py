"""Authenticated provider preferences. Secrets are configured by the operator in Render."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import get_current_user
from app.services import audit, personal_llm
from app.services.llm.base import StructuredAnalysisError

router = APIRouter(prefix="/personal", tags=["personal-llm"])


class PersonalLLMSettingsIn(BaseModel):
    # An old client must NOT be allowed to submit a cloudflared token,
    # Access service secret, personal LM key or arbitrary endpoint.
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(pattern="^(anthropic|openai_compatible)$")
    chat_model: str = Field(min_length=1, max_length=192)
    analysis_model: str = Field(min_length=1, max_length=192)
    copilot_model: str = Field(default="", max_length=192)
    max_tokens: int = Field(default=4096, ge=256, le=32768)
    timeout_seconds: int = Field(default=120, ge=5, le=5000)


@router.get("")
def read_personal_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return personal_llm.status(db, user.id)


@router.put("")
def update_personal_settings(
    payload: PersonalLLMSettingsIn,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
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
def delete_personal_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(personal_llm.UserLLMPreference, user.id)
    if row is not None:
        db.delete(row)
        db.commit()
    audit.log(db, actor_id=user.id, actor_role=user.role,
              action="personal_llm_settings_deleted", entity_type="llm_user_preferences",
              entity_id=user.id)
    return personal_llm.status(db, user.id)


@router.post("/test")
def test_personal_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Send only a synthetic prompt and return a whitelist of safe diagnostics."""
    try:
        from app.services.llm import build_provider
        provider = build_provider(personal_llm.resolve(db, user.id))
        answer = provider.chat("Responde solo OK.", [{"role": "user", "content": "OK"}], max_tokens=16)
        return {"ok": bool(answer.text.strip()), "detail": "Respuesta recibida." if answer.text.strip() else "El modelo devolvió una respuesta vacía."}
    except StructuredAnalysisError as exc:
        labels = {
            "http_401": "Autenticación rechazada (HTTP 401). Comprueba el token de LM Studio y Cloudflare Access.",
            "http_403": "Acceso denegado (HTTP 403). Comprueba la política Service Auth de Cloudflare.",
            "http_404": "Ruta o modelo no encontrado (HTTP 404). Comprueba el ID exacto del modelo en LM Studio.",
            "http_400": "Solicitud rechazada (HTTP 400). Comprueba el ID del modelo y los parámetros admitidos.",
            "local_endpoint_unreachable": "No se alcanza el servidor. Comprueba que cloudflared y LM Studio estén encendidos.",
            "local_endpoint_timeout": "Tiempo de espera agotado. Comprueba si el modelo está cargado.",
            "non_json_response": "Respuesta no JSON. Revisa que Cloudflare Access permita el Service Token del backend.",
        }
        return {"ok": False, "detail": labels.get(exc.error_code, "El proveedor ha rechazado la prueba. Revisa los registros seguros del backend.")}
    except (ValueError, RuntimeError):
        return {"ok": False, "detail": "El gateway no está listo. El administrador debe completar la configuración en Render."}
    except Exception:
        # Never relay exceptions or raw proxy responses: they may contain secrets.
        return {"ok": False, "detail": "Error de conexión no identificado. Revisa los registros seguros del backend."}

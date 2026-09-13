"""Audited runtime LLM selection from the Settings screen.

Any authenticated account may read which provider/model is active. Only
``admin_clinical`` may change it, and only when
``LLM_ALLOW_RUNTIME_OVERRIDE=true`` at deployment level. Endpoint topology is
redacted from non-admin accounts and model credentials always remain server
secrets.

The switch affects generative inference only. Consent, clinical storage,
audit and the deterministic risk engine are independent of the LLM. A failed
selected model never silently fails over to the other provider.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import (
    LLMEndpointConfigIn,
    LLMEndpointStatusOut,
    LLMEndpointTestIn,
    LLMEndpointTestOut,
)
from app.security import get_current_user, require_admin
from app.services import audit, llm_config
from app.services.llm import build_provider
from app.services.llm.base import StructuredAnalysisError
from app.services.llm.openai_compatible import PROVIDER_NAME as LOCAL_PROVIDER

logger = logging.getLogger("psychapp.llm_settings")

router = APIRouter(prefix="/api/v1/settings/llm", tags=["settings"])

WARNING_LOCAL = (
    "El texto destinado a inferencia se enviará al endpoint compatible con OpenAI seleccionado. "
    "El motor de riesgo sigue siendo determinista y no cambia."
)
WARNING_ANTHROPIC_KEY = (
    "Anthropic está seleccionado, pero falta ANTHROPIC_API_KEY en el servidor. "
    "La clave se configura como secreto del despliegue y nunca se devuelve al navegador."
)
WARNING_DISABLED = (
    "El cambio de proveedor está desactivado en este despliegue "
    "(LLM_ALLOW_RUNTIME_OVERRIDE=false)."
)
WARNING_NOT_ADMIN = (
    "Solo una cuenta de administración clínica puede cambiar el proveedor del modelo. "
    "Puedes ver qué modelo está activo, pero no modificarlo."
)

ADMIN_ROLE = "admin_clinical"


def _status(db: Session, user: User) -> LLMEndpointStatusOut:
    settings = get_settings()
    active = llm_config.resolve(db)
    environment = llm_config.environment_config()
    stored = llm_config.stored_override(db)
    allowed = settings.llm_allow_runtime_override
    is_admin = user.role == ADMIN_ROLE
    runtime = llm_config.backend_runtime()
    runtime_label = llm_config.backend_runtime_label()

    unreachable = bool(stored and stored.is_local and llm_config._is_unreachable_local(stored))
    if unreachable:
        notice = (
            "El endpoint local seleccionado no es alcanzable desde el backend. "
            "No se cambia automáticamente a Anthropic: las funciones que necesiten el LLM fallarán "
            "de forma controlada hasta que el endpoint vuelva a estar disponible o un administrador "
            "cambie explícitamente de proveedor."
        )
    elif active.is_local:
        notice = WARNING_LOCAL
    elif active.provider == llm_config.PROVIDER_ANTHROPIC and not active.api_key:
        notice = WARNING_ANTHROPIC_KEY
    elif not allowed:
        notice = WARNING_DISABLED
    elif not is_admin:
        notice = WARNING_NOT_ADMIN
    else:
        notice = None

    payload = active.public_dict()
    payload["backend_runtime"] = runtime
    payload["backend_runtime_label"] = runtime_label
    payload["local_endpoint_supported"] = runtime == "local"

    env_payload = environment.public_dict()
    env_payload["backend_runtime"] = runtime
    env_payload["backend_runtime_label"] = runtime_label
    env_payload["local_endpoint_supported"] = runtime == "local"

    # Endpoint hostnames are operational topology. Ordinary authenticated users
    # may know which model/provider answered, but only admin_clinical needs the
    # route itself to test or edit it.
    if not is_admin:
        payload["base_url"] = None
        env_payload["base_url"] = None

    return LLMEndpointStatusOut(
        active=payload,
        environment_default=env_payload,
        override_allowed=allowed,
        can_edit=allowed and is_admin,
        is_local=active.is_local,
        notice=notice,
        backend_runtime=runtime,
        backend_runtime_label=runtime_label,
        local_endpoint_supported=runtime == "local",
        ignored_override=None,
    )


@router.get("", response_model=LLMEndpointStatusOut)
def read_llm_settings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _status(db, user)


@router.put("", response_model=LLMEndpointStatusOut)
def update_llm_settings(
    payload: LLMEndpointConfigIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    settings = get_settings()
    if not settings.llm_allow_runtime_override:
        raise HTTPException(status_code=403, detail=WARNING_DISABLED)
    if payload.provider == llm_config.PROVIDER_ANTHROPIC and not settings.model_allow_commercial:
        raise HTTPException(
            status_code=422,
            detail="Anthropic no está aprobado en este despliegue (MODEL_ALLOW_COMMERCIAL=false).",
        )

    try:
        config = llm_config.set_active(
            db,
            provider=payload.provider,
            base_url=payload.base_url,
            chat_model=payload.chat_model,
            analysis_model=payload.analysis_model,
            copilot_model=payload.copilot_model,
            # Deliberately ignore any browser-supplied credential. Runtime
            # selection stores no secrets; adapters read deployment secrets.
            api_key=None,
            max_tokens=payload.max_tokens,
            timeout_seconds=payload.timeout_seconds,
            label=payload.label or "",
            actor_id=user.id,
        )
    except llm_config.LLMConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    audit.log(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="llm_endpoint_changed",
        entity_type="llm_endpoint_config",
        entity_id=config.config_id,
        extra={
            "provider": config.provider,
            "base_url": config.base_url,
            "chat_model": config.chat_model,
            "analysis_model": config.analysis_model,
            "copilot_model": config.copilot_model,
        },
    )
    return _status(db, user)


@router.delete("", response_model=LLMEndpointStatusOut)
def reset_llm_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    settings = get_settings()
    if not settings.llm_allow_runtime_override:
        raise HTTPException(status_code=403, detail=WARNING_DISABLED)
    llm_config.reset_to_environment(db)
    audit.log(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="llm_endpoint_reset",
        entity_type="llm_endpoint_config",
    )
    return _status(db, user)


@router.post("/test", response_model=LLMEndpointTestOut)
def test_llm_endpoint(
    payload: LLMEndpointTestIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Test a candidate provider without saving it or sending patient text."""
    settings = get_settings()
    if not settings.llm_allow_runtime_override:
        raise HTTPException(status_code=403, detail=WARNING_DISABLED)
    if payload.provider == llm_config.PROVIDER_ANTHROPIC and not settings.model_allow_commercial:
        raise HTTPException(
            status_code=422,
            detail="Anthropic no está aprobado en este despliegue (MODEL_ALLOW_COMMERCIAL=false).",
        )

    try:
        fields = llm_config.validate(
            provider=payload.provider,
            base_url=payload.base_url,
            chat_model=payload.chat_model,
            analysis_model=payload.analysis_model or payload.chat_model,
            copilot_model=payload.copilot_model,
            max_tokens=512,
            timeout_seconds=payload.timeout_seconds,
        )
    except llm_config.LLMConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    candidate = llm_config.ResolvedConfig(
        provider=fields["provider"],
        chat_model=fields["chat_model"],
        analysis_model=fields["analysis_model"],
        copilot_model=fields["copilot_model"],
        base_url=fields["base_url"],
        api_key=(settings.local_api_key if fields["provider"] == LOCAL_PROVIDER else settings.anthropic_api_key),
        max_tokens=512,
        timeout_seconds=payload.timeout_seconds,
    )
    provider = build_provider(candidate)

    audit.log(
        db,
        actor_id=user.id,
        actor_role=user.role,
        action="llm_endpoint_tested",
        entity_type="llm_endpoint_config",
        extra={"provider": candidate.provider, "base_url": candidate.base_url},
    )

    try:
        reply = provider.chat(
            "Responde solamente con la palabra OK.",
            [{"role": "user", "content": "Responde OK."}],
            max_tokens=16,
        ).text
    except StructuredAnalysisError as exc:
        return LLMEndpointTestOut(
            ok=False,
            detail=_test_failure_detail(exc.safe_kind, exc.error_code),
            error_code=exc.error_code,
            base_url=candidate.base_url,
        )
    except RuntimeError as exc:
        logger.warning("LLM endpoint test failed: %s", type(exc).__name__)
        detail = (
            "Falta ANTHROPIC_API_KEY en el secreto del servidor."
            if candidate.provider == llm_config.PROVIDER_ANTHROPIC
            else "Revisa la autenticación y la configuración segura del endpoint del modelo."
        )
        return LLMEndpointTestOut(
            ok=False,
            detail=detail,
            error_code=(
                "api_key_not_configured"
                if candidate.provider == LOCAL_PROVIDER
                else "anthropic_api_key_not_configured"
            ),
            base_url=candidate.base_url,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM endpoint test failed: %s", type(exc).__name__)
        return LLMEndpointTestOut(
            ok=False,
            detail=f"No se pudo contactar con el endpoint ({type(exc).__name__}).",
            base_url=candidate.base_url,
        )

    sample = (reply or "").strip()
    return LLMEndpointTestOut(
        ok=bool(sample),
        detail=(
            f"El servidor respondió: «{sample[:120]}»"
            if sample
            else "El servidor respondió, pero con un mensaje vacío. Revisa el nombre del modelo."
        ),
        sample=sample[:400] or None,
        base_url=candidate.base_url,
    )


def _test_failure_detail(safe_kind: str, error_code: str | None) -> str:
    if error_code == "local_endpoint_unreachable":
        if llm_config.backend_runtime() == "cloud":
            return (
                f"Este backend corre en {llm_config.backend_runtime_label()} y no alcanzó el "
                "servidor del modelo. Usa un túnel HTTPS público y autenticado."
            )
        return (
            "No se llegó al servidor del modelo. Comprueba que el servidor local está "
            "arrancado y que la URI coincide con la que está escuchando."
        )
    if error_code == "local_endpoint_timeout":
        return "El servidor no respondió a tiempo. Revisa la carga del modelo o aumenta el tiempo de espera."
    if error_code == "api_key_not_configured":
        return "El endpoint requiere autenticación y no hay un token configurado en el servidor."
    if error_code == "http_404":
        return "El servidor respondió 404. Revisa el sufijo /v1 y el identificador del modelo."
    if error_code in ("http_401", "http_403"):
        return "El servidor rechazó la autenticación. Revisa el token del endpoint."
    if safe_kind == "configuration_error":
        return "Configuración rechazada por el servidor. Revisa URL, autenticación y nombre del modelo."
    return f"El endpoint devolvió un error ({error_code or safe_kind})."

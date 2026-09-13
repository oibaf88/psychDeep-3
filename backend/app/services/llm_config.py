"""Resolve and audit the LLM deployment selected at runtime.

PsychDeep vNext keeps clinical storage, consent, deterministic risk and audit
independent from the generative model. The deployment supplies approved model
endpoints and secrets, while an ``admin_clinical`` may switch between Anthropic
and an OpenAI-compatible local/tunnel endpoint when
``LLM_ALLOW_RUNTIME_OVERRIDE`` is enabled.

Runtime changes are append-only rows in ``llm_endpoint_configs``: the previous
row is deactivated and the new selection is recorded. Credentials are never
stored in these rows; they remain server-side environment secrets.

A selected model never silently fails over to the other provider. If the
chosen endpoint is unavailable, model-dependent functions fail safely while
clinical data, deterministic safety and static crisis resources continue to
work.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from ipaddress import ip_address
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import LLMEndpointConfig

logger = logging.getLogger("psychapp.llm_config")

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_LOCAL = "openai_compatible"
PROVIDERS = (PROVIDER_LOCAL, PROVIDER_ANTHROPIC)

CACHE_TTL_SECONDS = 30.0
MAX_TOKENS_MIN, MAX_TOKENS_MAX = 256, 32768
TIMEOUT_MIN, TIMEOUT_MAX = 5, 5000

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}


@dataclass(frozen=True)
class ResolvedConfig:
    """The configuration in force for one call, whatever its source."""

    provider: str
    chat_model: str
    analysis_model: str
    copilot_model: str = ""
    copilot_model_explicit: str = ""
    base_url: str | None = None
    api_key: str = ""
    max_tokens: int = 4096
    timeout_seconds: int = 120
    label: str = ""
    source: str = "environment"  # environment | runtime
    config_id: str | None = None
    updated_at: datetime | None = None

    @property
    def is_local(self) -> bool:
        return self.provider == PROVIDER_LOCAL

    @property
    def explicit_max_tokens(self) -> int | None:
        return self.max_tokens if self.source == "runtime" else None

    @property
    def copilot_model_is_inherited(self) -> bool:
        return not self.copilot_model_explicit.strip()

    def public_dict(self) -> dict:
        """Everything the authenticated UI may see. Never serialise a key."""
        settings = get_settings()
        if self.provider == PROVIDER_ANTHROPIC:
            has_key = bool(settings.anthropic_api_key)
            provider_label = "Claude / API de Anthropic"
        else:
            has_key = bool(settings.local_api_key)
            provider_label = "Modelo local / API compatible con OpenAI"
        return {
            "provider": self.provider,
            "provider_label": provider_label,
            "label": self.label,
            "base_url": self.base_url,
            "chat_model": self.chat_model,
            "analysis_model": self.analysis_model,
            "copilot_model": self.copilot_model or self.chat_model,
            "copilot_model_explicit": self.copilot_model_explicit,
            "copilot_model_is_inherited": self.copilot_model_is_inherited,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "source": self.source,
            "config_id": self.config_id,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "has_api_key": has_key,
            "uses_server_api_key": True,
        }


class LLMConfigError(ValueError):
    """The submitted configuration cannot be used."""


def backend_runtime() -> str:
    if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"):
        return "cloud"
    if get_settings().is_production:
        return "cloud"
    return "local"


def backend_runtime_label() -> str:
    if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"):
        region = os.environ.get("RENDER_REGION") or "frankfurt"
        return f"Render ({region})"
    if get_settings().is_production:
        return "servidor en la nube"
    return "este equipo (proceso local de FastAPI)"


def _hostname_is_private(hostname: str) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    if not host:
        return True
    if host in LOOPBACK_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        return True
    try:
        ip = ip_address(host)
    except ValueError:
        return False
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)


def endpoint_reachability(url: str | None) -> dict:
    """Validate whether this FastAPI runtime can route safely to ``url``."""
    runtime = backend_runtime()
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").lower()
    private = _hostname_is_private(host)
    if runtime == "local":
        return {"ok": True, "runtime": runtime, "private_target": private, "reason": None}
    if not url:
        return {
            "ok": False,
            "runtime": runtime,
            "private_target": True,
            "reason": "Falta la URL del modelo.",
        }
    if private:
        return {
            "ok": False,
            "runtime": runtime,
            "private_target": True,
            "reason": (
                f"Este backend corre en {backend_runtime_label()} y no tiene ruta a {host}. "
                "Una IP de LAN no es alcanzable desde Render. Usa un túnel HTTPS "
                "público y autenticado que apunte al servidor local del modelo."
            ),
        }
    if parsed.scheme != "https":
        return {
            "ok": False,
            "runtime": runtime,
            "private_target": False,
            "reason": (
                "Desde un despliegue en la nube el endpoint del modelo tiene que ser "
                "HTTPS público. HTTP en claro enviaría texto clínico sin cifrar."
            ),
        }
    return {"ok": True, "runtime": runtime, "private_target": False, "reason": None}


def _is_unreachable_local(config: ResolvedConfig) -> bool:
    return bool(config.is_local and not endpoint_reachability(config.base_url)["ok"])


_lock = threading.Lock()
_cached: tuple[float, ResolvedConfig] | None = None


def invalidate_cache() -> None:
    global _cached
    with _lock:
        _cached = None


def _anthropic_environment(settings) -> ResolvedConfig:
    return ResolvedConfig(
        provider=PROVIDER_ANTHROPIC,
        chat_model=settings.anthropic_chat_model,
        analysis_model=settings.anthropic_analysis_model,
        copilot_model=settings.copilot_model,
        copilot_model_explicit=settings.anthropic_copilot_model.strip(),
        api_key=settings.anthropic_api_key,
        max_tokens=settings.anthropic_max_tokens,
        timeout_seconds=settings.llm_openai_compatible_timeout_seconds,
        label="Claude configurado en el despliegue",
        source="environment",
    )


def _local_environment(settings, *, cloud_tuned: bool = False) -> ResolvedConfig:
    if cloud_tuned:
        chat_model = settings.model_cloud_chat_model.strip()
        analysis_model = settings.model_cloud_analysis_model.strip() or chat_model
        copilot_model = settings.model_cloud_copilot_model.strip() or chat_model
        return ResolvedConfig(
            provider=PROVIDER_LOCAL,
            chat_model=chat_model,
            analysis_model=analysis_model,
            copilot_model=copilot_model,
            copilot_model_explicit=settings.model_cloud_copilot_model.strip(),
            base_url=settings.model_cloud_base_url.strip() or None,
            api_key=settings.model_cloud_api_key,
            max_tokens=settings.model_cloud_max_tokens,
            timeout_seconds=settings.model_cloud_timeout_seconds,
            label="Modelo cloud privado configurado en el despliegue",
            source="environment",
        )
    return ResolvedConfig(
        provider=PROVIDER_LOCAL,
        chat_model=settings.local_chat_model,
        analysis_model=settings.local_analysis_model,
        copilot_model=settings.local_copilot_model,
        copilot_model_explicit=settings.model_local_copilot_model.strip() or settings.llm_openai_compatible_copilot_model.strip(),
        base_url=settings.local_base_url.strip() or None,
        api_key=settings.local_api_key,
        max_tokens=settings.model_local_max_tokens or settings.llm_openai_compatible_max_tokens,
        timeout_seconds=settings.model_local_timeout_seconds or settings.llm_openai_compatible_timeout_seconds,
        label="Modelo local/túnel configurado en el despliegue",
        source="environment",
    )


def environment_config() -> ResolvedConfig:
    """Return the deployment default used when no runtime override is active."""
    settings = get_settings()
    alias = settings.model_deployment_alias.strip()
    if alias == "commercial-approved":
        return _anthropic_environment(settings)
    if alias == "cloud-tuned":
        return _local_environment(settings, cloud_tuned=True)
    if alias == "local-tunnel":
        return _local_environment(settings)

    # Compatibility with deployments predating Model Gateway aliases.
    if settings.llm_default_provider == PROVIDER_ANTHROPIC:
        return _anthropic_environment(settings)
    return ResolvedConfig(
        provider=PROVIDER_LOCAL,
        chat_model=settings.llm_openai_compatible_chat_model,
        analysis_model=settings.llm_openai_compatible_analysis_model,
        copilot_model=settings.local_copilot_model,
        copilot_model_explicit=settings.llm_openai_compatible_copilot_model.strip(),
        base_url=settings.llm_openai_compatible_base_url.strip() or None,
        api_key=settings.llm_openai_compatible_api_key,
        max_tokens=settings.llm_openai_compatible_max_tokens,
        timeout_seconds=settings.llm_openai_compatible_timeout_seconds,
        label="Modelo OpenAI-compatible configurado en el despliegue",
        source="environment",
    )


def _from_row(row: LLMEndpointConfig) -> ResolvedConfig:
    settings = get_settings()
    api_key = settings.anthropic_api_key if row.provider == PROVIDER_ANTHROPIC else settings.local_api_key
    return ResolvedConfig(
        provider=row.provider,
        chat_model=row.chat_model,
        analysis_model=row.analysis_model,
        copilot_model=row.copilot_model or row.chat_model,
        copilot_model_explicit=row.copilot_model or "",
        base_url=row.base_url,
        api_key=api_key,
        max_tokens=row.max_tokens,
        timeout_seconds=row.timeout_seconds,
        label=row.label or "",
        source="runtime",
        config_id=str(row.id),
        updated_at=row.created_at,
    )


def active_row(db: Session) -> LLMEndpointConfig | None:
    return (
        db.query(LLMEndpointConfig)
        .filter(LLMEndpointConfig.is_active == True)  # noqa: E712
        .order_by(LLMEndpointConfig.created_at.desc())
        .first()
    )


def stored_override(db: Session | None) -> ResolvedConfig | None:
    if db is None:
        return None
    try:
        row = active_row(db)
    except Exception:  # noqa: BLE001
        return None
    return _from_row(row) if row else None


def resolve(db: Session | None = None) -> ResolvedConfig:
    """Return the model configuration currently selected for inference.

    Database lookup failures fall back to the deployment default because the
override cannot be established. A *valid stored selection*, however, is
never silently replaced by the other provider merely because its endpoint
is unavailable.
    """
    global _cached
    settings = get_settings()
    if not settings.llm_allow_runtime_override:
        return environment_config()

    now = time.monotonic()
    with _lock:
        if _cached and now - _cached[0] < CACHE_TTL_SECONDS:
            return _cached[1]

    if db is None:
        with _lock:
            if _cached:
                return _cached[1]
        return environment_config()

    try:
        row = active_row(db)
        config = _from_row(row) if row else environment_config()
    except Exception:  # noqa: BLE001
        logger.exception("Could not read the active LLM configuration; using deployment default")
        return environment_config()

    if config.source == "runtime" and _is_unreachable_local(config):
        logger.warning(
            "Selected local LLM endpoint %s is not reachable from %s; no provider fallback will be attempted",
            config.base_url,
            backend_runtime_label(),
        )

    with _lock:
        _cached = (now, config)
    return config


def normalise_base_url(raw: str) -> str:
    url = (raw or "").strip().rstrip("/")
    if not url:
        raise LLMConfigError("Escribe la URL del servidor.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise LLMConfigError("La URL tiene que empezar por http:// o https://")
    if not parsed.netloc:
        raise LLMConfigError("La URL no incluye un servidor.")
    if url.endswith("/chat/completions"):
        url = url[: -len("/chat/completions")]
    if url.endswith("/api/v1/chat"):
        url = url[: -len("/api/v1/chat")] + "/v1"
    elif url.endswith("/api/v1"):
        url = url[: -len("/api/v1")] + "/v1"
    if not urlparse(url).path.rstrip("/"):
        url = f"{url}/v1"
    return url


def validate(
    *,
    provider: str,
    base_url: str | None,
    chat_model: str,
    analysis_model: str,
    max_tokens: int,
    timeout_seconds: int,
    copilot_model: str | None = None,
) -> dict:
    if provider not in PROVIDERS:
        raise LLMConfigError("Selecciona Anthropic o un endpoint compatible con OpenAI.")
    if not chat_model.strip() or not analysis_model.strip():
        raise LLMConfigError("Indica el nombre del modelo para el chat y para el análisis.")
    if not MAX_TOKENS_MIN <= max_tokens <= MAX_TOKENS_MAX:
        raise LLMConfigError(f"max_tokens tiene que estar entre {MAX_TOKENS_MIN} y {MAX_TOKENS_MAX}.")
    if not TIMEOUT_MIN <= timeout_seconds <= TIMEOUT_MAX:
        raise LLMConfigError(f"El tiempo de espera tiene que estar entre {TIMEOUT_MIN} y {TIMEOUT_MAX} segundos.")

    if provider == PROVIDER_ANTHROPIC:
        return {
            "provider": provider,
            "base_url": None,
            "chat_model": chat_model.strip(),
            "analysis_model": analysis_model.strip(),
            "copilot_model": (copilot_model or "").strip(),
            "max_tokens": max_tokens,
            "timeout_seconds": timeout_seconds,
        }

    normalised = normalise_base_url(base_url or "")
    reach = endpoint_reachability(normalised)
    if not reach["ok"]:
        raise LLMConfigError(reach["reason"])
    return {
        "provider": provider,
        "base_url": normalised,
        "chat_model": chat_model.strip(),
        "analysis_model": analysis_model.strip(),
        "copilot_model": (copilot_model or "").strip(),
        "max_tokens": max_tokens,
        "timeout_seconds": timeout_seconds,
    }


def set_active(
    db: Session,
    *,
    provider: str,
    base_url: str | None,
    chat_model: str,
    analysis_model: str,
    api_key: str | None,
    max_tokens: int,
    timeout_seconds: int,
    label: str,
    copilot_model: str | None = None,
    actor_id=None,
) -> ResolvedConfig:
    """Insert a new active configuration and retire the previous one.

    ``api_key`` is accepted for API compatibility but deliberately ignored:
    model credentials remain server-side deployment secrets.
    """
    fields = validate(
        provider=provider,
        base_url=base_url,
        chat_model=chat_model,
        analysis_model=analysis_model,
        copilot_model=copilot_model,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )

    now = datetime.utcnow()
    for row in db.query(LLMEndpointConfig).filter(LLMEndpointConfig.is_active == True).all():  # noqa: E712
        row.is_active = False
        row.deactivated_at = now
    db.flush()

    record = LLMEndpointConfig(
        provider=fields["provider"],
        base_url=fields["base_url"],
        chat_model=fields["chat_model"],
        analysis_model=fields["analysis_model"],
        copilot_model=fields["copilot_model"] or None,
        api_key=None,
        max_tokens=fields["max_tokens"],
        timeout_seconds=fields["timeout_seconds"],
        label=(label or "").strip()[:120],
        is_active=True,
        created_by=actor_id,
        created_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    invalidate_cache()
    return _from_row(record)


def reset_to_environment(db: Session) -> ResolvedConfig:
    """Deactivate runtime selection and return to the deployment default."""
    now = datetime.utcnow()
    for row in db.query(LLMEndpointConfig).filter(LLMEndpointConfig.is_active == True).all():  # noqa: E712
        row.is_active = False
        row.deactivated_at = now
    db.commit()
    invalidate_cache()
    return environment_config()

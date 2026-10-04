"""Account-scoped model selection and LM Studio authentication.

Cloudflare Access's service-token pair is operator-owned and stored only in
Render. The cloudflared connector token stays on Windows. Each authenticated
user supplies their own LM Studio bearer token, encrypted at rest with a
stable Fernet key held solely by the backend. Never use a shared LM Studio key
as a fallback for an account that has no personal token.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.config import get_settings
from app.database import Base
from app.services import llm_config
from app.services.local_model_catalog import (
    Catalog,
    fetch_catalog,
    select_model,
)


class LocalModelUnavailable(RuntimeError):
    """The tunnel answered, but no usable LM Studio model id is selected."""


OPENAI_BASE_URL = "https://api.openai.com/v1"


class UserLLMPreference(Base):
    __tablename__ = "llm_user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500))
    chat_model: Mapped[str] = mapped_column(String(192), nullable=False)
    analysis_model: Mapped[str] = mapped_column(String(192), nullable=False)
    copilot_model: Mapped[str] = mapped_column(String(192), nullable=False, default="")
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=4096)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    lm_api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    # Legacy personal Access columns retained for rollback only; never read.
    cf_client_id_encrypted: Mapped[str | None] = mapped_column(Text)
    cf_client_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PersonalResolvedConfig(llm_config.ResolvedConfig):
    """Hide bearer and Access credentials from dataclass repr / API responses."""

    api_key: str = field(default="", repr=False)
    access_client_id: str = field(default="", repr=False)
    access_client_secret: str = field(default="", repr=False)
    access_hostname: str = ""


def _cipher() -> Fernet:
    key = os.environ.get("LLM_USER_CREDENTIALS_KEY", "").strip()
    if not key:
        raise RuntimeError("El cifrado de credenciales no está configurado en el servidor.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise RuntimeError("La clave de cifrado del servidor no es válida.") from exc


def _replace_lm_key(value: str | None, old_ciphertext: str | None) -> str | None:
    """None preserves, empty string revokes, nonempty value creates/rotates."""
    if value is None:
        return old_ciphertext
    if not value.strip():
        return None
    if len(value) > 8192 or "\r" in value or "\n" in value:
        raise ValueError("Formato de API key de LM Studio no válido.")
    return _cipher().encrypt(value.strip().encode("utf-8")).decode("ascii")


def _decrypt_lm_key(ciphertext: str | None) -> str:
    if not ciphertext:
        raise RuntimeError("Configura tu API key personal de LM Studio antes de usar el modelo.")
    try:
        return _cipher().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise RuntimeError("No se pueden descifrar las credenciales de esta cuenta. Solicita su rotación.") from exc


def approved_host() -> str:
    host = get_settings().model_local_cf_access_host.strip().lower().rstrip(".")
    if not host:
        raise ValueError("El administrador debe configurar el host de Cloudflare Access en Render.")
    return host


def approved_endpoint(raw: str) -> str:
    """Only an operator-pinned HTTPS /v1 endpoint may receive either secret."""
    url = llm_config.normalise_base_url(raw)
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != approved_host()
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.query or parsed.fragment
        or parsed.path.rstrip("/") != "/v1"
    ):
        raise ValueError("El endpoint HTTPS /v1 de Render no coincide con el host autorizado.")
    return url


def shared_gateway():
    """Fail closed unless operator-owned Cloudflare Access is complete."""
    settings = get_settings()
    if not settings.model_local_cf_access_required:
        raise RuntimeError("El administrador debe exigir Cloudflare Access en Render.")
    if not all((
        settings.model_local_cf_access_host.strip(),
        settings.model_local_cf_access_client_id.strip(),
        settings.model_local_cf_access_client_secret.strip(),
    )):
        raise RuntimeError("El administrador debe completar Cloudflare Access en Render.")
    return settings, approved_endpoint(settings.model_local_base_url)


def shared_ready() -> bool:
    try:
        shared_gateway()
        return True
    except (ValueError, RuntimeError):
        return False


def _catalog_for(api_key: str) -> Catalog:
    """Catalog of the operator tunnel. Never uses the shared LM Studio key."""
    try:
        settings, endpoint = shared_gateway()
    except (ValueError, RuntimeError):
        return Catalog((), False)
    if not api_key.strip():
        return Catalog((), False)
    return fetch_catalog(
        endpoint=endpoint,
        api_key=api_key,
        access_client_id=settings.model_local_cf_access_client_id,
        access_client_secret=settings.model_local_cf_access_client_secret,
        access_hostname=settings.model_local_cf_access_host,
    )


def _usable_key(ciphertext: str | None) -> str:
    try:
        return _decrypt_lm_key(ciphertext)
    except RuntimeError:
        return ""


def _catalog_payload(catalog: Catalog) -> list[dict]:
    return [{"id": model.id, "loaded": model.loaded} for model in catalog.models]


def _is_openai_destination(row: UserLLMPreference | None) -> bool:
    return bool(
        row
        and row.provider == llm_config.PROVIDER_LOCAL
        and (row.base_url or "").rstrip("/") == OPENAI_BASE_URL
    )


def _admin_owner_id(db: Session) -> uuid.UUID | None:
    """Latest active clinical-admin connection, when this session can query it."""
    from app.models import User

    query = getattr(db, "query", None)
    if not callable(query):
        return None
    row = (
        db.query(UserLLMPreference)
        .join(User, User.id == UserLLMPreference.user_id)
        .filter(User.role == "admin_clinical", User.is_active == True)  # noqa: E712
        .order_by(UserLLMPreference.updated_at.desc().nullslast())
        .first()
    )
    return row.user_id if row is not None else None


def _commercial_admin_id(db: Session) -> uuid.UUID | None:
    """Admin connection when it is Codex or Anthropic.

    Those providers use server credentials. A local LM Studio row stays on
    the account that stored its own key and must not replace another account.
    """
    owner = _admin_owner_id(db)
    if owner is None:
        return None
    row = db.get(UserLLMPreference, owner)
    if row is None:
        return None
    if row.provider == llm_config.PROVIDER_ANTHROPIC or _is_openai_destination(row):
        return owner
    return None


def status(db: Session, user_id: uuid.UUID) -> dict:
    row = db.get(UserLLMPreference, user_id)
    settings = get_settings()
    selected = row.provider if row else llm_config.PROVIDER_LOCAL
    openai = _is_openai_destination(row)
    local = selected == llm_config.PROVIDER_LOCAL and not openai
    logical_provider = "openai" if openai else selected
    # Codex and Anthropic do not need the LM Studio catalog. Asking the
    # tunnel here makes the admin screen depend on Cloudflare while the
    # saved connection is a server provider.
    catalog = (
        _catalog_for(_usable_key(row.lm_api_key_encrypted if row else None))
        if local
        else Catalog((), False)
    )
    # Local inference follows the model loaded on the operator's computer.
    # A stored id is not a menu choice and is not shown as one.
    effective = select_model("", catalog) if local else ""
    loaded = next((model.id for model in catalog.models if model.loaded), "")
    if not loaded and len(catalog.models) == 1:
        loaded = catalog.models[0].id
    return {
        "configured": row is not None,
        "provider": logical_provider,
        "chat_model": (
            "" if local
            else settings.openai_chat_model if openai
            else settings.anthropic_chat_model if row and row.provider == llm_config.PROVIDER_ANTHROPIC
            else ""
        ),
        "analysis_model": (
            "" if local
            else settings.openai_analysis_model if openai
            else settings.anthropic_analysis_model if row and row.provider == llm_config.PROVIDER_ANTHROPIC
            else ""
        ),
        "effective_local_model": effective,
        "copilot_model": (
            "" if local
            else settings.openai_copilot_model or settings.openai_chat_model if openai
            else row.copilot_model
        ),
        "default_local_chat_model": loaded,
        "default_local_analysis_model": loaded,
        "local_models": _catalog_payload(catalog),
        "local_models_reachable": catalog.reachable,
        "max_tokens": row.max_tokens if row else min(settings.model_local_max_tokens, 32768),
        "timeout_seconds": row.timeout_seconds if row else settings.model_local_timeout_seconds,
        "local_available": shared_ready(),
        "lm_api_key_configured": bool(row and row.lm_api_key_encrypted),
        "anthropic_allowed": bool(settings.model_allow_commercial and settings.anthropic_api_key),
        "openai_allowed": bool(settings.openai_api_key),
    }


def save(db: Session, user_id: uuid.UUID, payload) -> dict:
    settings = get_settings()
    if payload.provider == llm_config.PROVIDER_ANTHROPIC:
        if not settings.model_allow_commercial or not settings.anthropic_api_key:
            raise ValueError("Anthropic no está habilitado por el administrador.")
        endpoint = None
        chat_model = settings.anthropic_chat_model
        analysis_model = settings.anthropic_analysis_model
        copilot_model = settings.anthropic_copilot_model or chat_model
    elif payload.provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OpenAI no está habilitado: falta OPENAI_API_KEY en Render.")
        # The OpenAI destination and model ids are server-owned. The account
        # selects the provider, never an arbitrary URL or model name.
        endpoint = OPENAI_BASE_URL
        chat_model = settings.openai_chat_model
        analysis_model = settings.openai_analysis_model
        copilot_model = settings.openai_copilot_model or chat_model
    else:
        _, endpoint = shared_gateway()
        # Ignore any model id from the request. Inference reads the model
        # loaded in LM Studio on the operator's computer.
        chat_model, analysis_model, copilot_model = "", "", ""
    if payload.provider == "openai":
        fields = {
            "provider": llm_config.PROVIDER_LOCAL,
            "base_url": endpoint,
            "chat_model": chat_model.strip(),
            "analysis_model": analysis_model.strip(),
            "copilot_model": copilot_model.strip(),
            "max_tokens": payload.max_tokens,
            "timeout_seconds": payload.timeout_seconds,
        }
    else:
        # An empty local id is valid: inference reads the model loaded in LM Studio.
        # validate() still checks the pinned tunnel URL, tokens and timeout.
        placeholder = chat_model.strip() or "pending-model"
        fields = llm_config.validate(
            provider=payload.provider, base_url=endpoint, chat_model=placeholder,
            analysis_model=analysis_model.strip() or placeholder, copilot_model=copilot_model,
            max_tokens=payload.max_tokens, timeout_seconds=payload.timeout_seconds,
        )
        if payload.provider == llm_config.PROVIDER_LOCAL:
            fields["chat_model"] = chat_model.strip()
            fields["analysis_model"] = analysis_model.strip()
            fields["copilot_model"] = ""
    row = db.get(UserLLMPreference, user_id)
    old_ciphertext = row.lm_api_key_encrypted if row else None
    lm_ciphertext = _replace_lm_key(payload.lm_api_key, old_ciphertext)
    if payload.provider == llm_config.PROVIDER_LOCAL and not lm_ciphertext:
        raise ValueError("Introduce tu API key personal de LM Studio para activar el modelo local.")
    # Validate encryption availability before accepting any newly supplied key.
    if payload.lm_api_key is not None and payload.lm_api_key.strip():
        _cipher()
    if row is None:
        row = UserLLMPreference(user_id=user_id, provider=fields["provider"],
                                chat_model=fields["chat_model"], analysis_model=fields["analysis_model"])
    row.provider = llm_config.PROVIDER_LOCAL if payload.provider == "openai" else fields["provider"]
    row.base_url = fields["base_url"] if payload.provider == "openai" else None  # OpenAI is a fixed server-owned destination.
    row.chat_model = fields["chat_model"]
    row.analysis_model = fields["analysis_model"]
    row.copilot_model = fields["copilot_model"]
    row.max_tokens = fields["max_tokens"]
    row.timeout_seconds = fields["timeout_seconds"]
    row.lm_api_key_encrypted = lm_ciphertext
    # Obsolete per-account Access credentials are never used for inference.
    row.cf_client_id_encrypted = None
    row.cf_client_secret_encrypted = None
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    return status(db, user_id)


def resolve(db: Session, user_id: uuid.UUID) -> PersonalResolvedConfig:
    row = db.get(UserLLMPreference, user_id)
    settings = get_settings()
    selected = row.provider if row else llm_config.PROVIDER_LOCAL
    openai = _is_openai_destination(row)
    if selected == llm_config.PROVIDER_ANTHROPIC:
        if not settings.model_allow_commercial or not settings.anthropic_api_key:
            raise RuntimeError("Anthropic no está habilitado por el administrador.")
        return PersonalResolvedConfig(
            provider=selected,
            chat_model=settings.anthropic_chat_model,
            analysis_model=settings.anthropic_analysis_model,
            copilot_model=settings.anthropic_copilot_model or settings.anthropic_chat_model,
            copilot_model_explicit=row.copilot_model, api_key=settings.anthropic_api_key,
            max_tokens=row.max_tokens, timeout_seconds=row.timeout_seconds,
            label="Selección de cuenta", source="runtime",
        )
    if openai:
        if not settings.openai_api_key:
            raise RuntimeError("OpenAI no está habilitado: falta OPENAI_API_KEY en Render.")
        return PersonalResolvedConfig(
            provider="openai",
            chat_model=settings.openai_chat_model,
            analysis_model=settings.openai_analysis_model,
            copilot_model=settings.openai_copilot_model or settings.openai_chat_model,
            copilot_model_explicit=row.copilot_model,
            api_key=settings.openai_api_key,
            max_tokens=row.max_tokens,
            timeout_seconds=row.timeout_seconds,
            label="OpenAI / API de OpenAI",
            source="runtime",
        )
    if selected != llm_config.PROVIDER_LOCAL:
        raise RuntimeError("Proveedor personal no autorizado.")
    settings, endpoint = shared_gateway()
    api_key = _decrypt_lm_key(row.lm_api_key_encrypted if row else None)
    model = select_model("", _catalog_for(api_key))
    if not model:
        raise LocalModelUnavailable(
            "No hay un modelo cargado en el ordenador. Carga uno en LM Studio; desde PsychDeep no se elige un modelo."
        )
    return PersonalResolvedConfig(
        provider=selected, base_url=endpoint, chat_model=model,
        analysis_model=model,
        copilot_model=model,
        copilot_model_explicit="", api_key=api_key,
        max_tokens=row.max_tokens if row else min(settings.model_local_max_tokens, 32768),
        timeout_seconds=row.timeout_seconds if row else settings.model_local_timeout_seconds,
        label="Modelo local con credenciales personales", source="runtime",
        access_client_id=settings.model_local_cf_access_client_id,
        access_client_secret=settings.model_local_cf_access_client_secret,
        access_hostname=approved_host(),
    )


def resolve_active(db: Session, user_id: uuid.UUID) -> PersonalResolvedConfig:
    """Inference connection for this request.

    When the clinical admin has saved Codex or Anthropic, every account uses
    that connection. Patient chat must not keep calling the local tunnel
    after that selection. A local connection still resolves for the account
    that owns the LM Studio key.
    """
    owner = _commercial_admin_id(db)
    return resolve(db, owner if owner is not None else user_id)

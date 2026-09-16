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


def status(db: Session, user_id: uuid.UUID) -> dict:
    row = db.get(UserLLMPreference, user_id)
    settings = get_settings()
    selected = row.provider if row else llm_config.PROVIDER_LOCAL
    local = selected == llm_config.PROVIDER_LOCAL
    return {
        "configured": row is not None,
        "provider": selected,
        "chat_model": settings.local_chat_model if local else row.chat_model,
        "analysis_model": settings.local_analysis_model if local else row.analysis_model,
        "copilot_model": "" if local else row.copilot_model,
        "default_local_chat_model": settings.local_chat_model,
        "default_local_analysis_model": settings.local_analysis_model,
        "max_tokens": row.max_tokens if row else min(settings.model_local_max_tokens, 32768),
        "timeout_seconds": row.timeout_seconds if row else settings.model_local_timeout_seconds,
        "local_available": shared_ready(),
        "lm_api_key_configured": bool(row and row.lm_api_key_encrypted),
        "anthropic_allowed": bool(settings.model_allow_commercial and settings.anthropic_api_key),
    }


def save(db: Session, user_id: uuid.UUID, payload) -> dict:
    settings = get_settings()
    if payload.provider == llm_config.PROVIDER_ANTHROPIC:
        if not settings.model_allow_commercial or not settings.anthropic_api_key:
            raise ValueError("Anthropic no está habilitado por el administrador.")
        endpoint = None
        chat_model, analysis_model, copilot_model = payload.chat_model, payload.analysis_model, payload.copilot_model
    else:
        _, endpoint = shared_gateway()
        # Only the operator's pinned local model IDs are authoritative.
        chat_model, analysis_model, copilot_model = settings.local_chat_model, settings.local_analysis_model, ""
    fields = llm_config.validate(
        provider=payload.provider, base_url=endpoint, chat_model=chat_model,
        analysis_model=analysis_model, copilot_model=copilot_model,
        max_tokens=payload.max_tokens, timeout_seconds=payload.timeout_seconds,
    )
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
    row.provider = fields["provider"]
    row.base_url = None  # Never persist a user-controlled destination.
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
    if selected == llm_config.PROVIDER_ANTHROPIC:
        if not settings.model_allow_commercial or not settings.anthropic_api_key:
            raise RuntimeError("Anthropic no está habilitado por el administrador.")
        return PersonalResolvedConfig(
            provider=selected, chat_model=row.chat_model, analysis_model=row.analysis_model,
            copilot_model=row.copilot_model or row.chat_model,
            copilot_model_explicit=row.copilot_model, api_key=settings.anthropic_api_key,
            max_tokens=row.max_tokens, timeout_seconds=row.timeout_seconds,
            label="Selección de cuenta", source="runtime",
        )
    if selected != llm_config.PROVIDER_LOCAL:
        raise RuntimeError("Proveedor personal no autorizado.")
    settings, endpoint = shared_gateway()
    api_key = _decrypt_lm_key(row.lm_api_key_encrypted if row else None)
    return PersonalResolvedConfig(
        provider=selected, base_url=endpoint, chat_model=settings.local_chat_model,
        analysis_model=settings.local_analysis_model,
        copilot_model=settings.local_copilot_model,
        copilot_model_explicit="", api_key=api_key,
        max_tokens=row.max_tokens if row else min(settings.model_local_max_tokens, 32768),
        timeout_seconds=row.timeout_seconds if row else settings.model_local_timeout_seconds,
        label="Modelo local con credenciales personales", source="runtime",
        access_client_id=settings.model_local_cf_access_client_id,
        access_client_secret=settings.model_local_cf_access_client_secret,
        access_hostname=approved_host(),
    )

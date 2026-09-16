"""Account-specific provider choices; gateway credentials exist ONLY in Render.

The connector token authenticates the Windows cloudflared process and is never
an HTTP credential. Render supplies one Cloudflare Access service-token pair
and one LM Studio bearer token. Authenticated users choose models/providers but
cannot submit, retrieve, replace, or redirect those shared credentials.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

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
    # Legacy encrypted fields remain mapped solely for a safe, staged rollout.
    # Never read these fields for inference or populate them on new writes.
    lm_api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    cf_client_id_encrypted: Mapped[str | None] = mapped_column(Text)
    cf_client_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PersonalResolvedConfig(llm_config.ResolvedConfig):
    """Per-user model choice paired with operator-owned server secrets."""

    access_client_id: str = ""
    access_client_secret: str = ""
    access_hostname: str = ""


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
    """Fail closed until BOTH independent authentication layers are configured."""
    settings = get_settings()
    if not settings.model_local_cf_access_required:
        raise RuntimeError("El administrador debe exigir Cloudflare Access en Render.")
    if not all((
        settings.model_local_cf_access_host.strip(),
        settings.model_local_cf_access_client_id.strip(),
        settings.model_local_cf_access_client_secret.strip(),
        settings.model_local_api_key.strip(),
    )):
        raise RuntimeError("El administrador debe completar los secretos de Cloudflare Access y LM Studio en Render.")
    endpoint = approved_endpoint(settings.model_local_base_url)
    return settings, endpoint


def shared_ready() -> bool:
    try:
        shared_gateway()
        return True
    except (ValueError, RuntimeError):
        return False


def status(db: Session, user_id: uuid.UUID) -> dict:
    row = db.get(UserLLMPreference, user_id)
    settings = get_settings()
    ready = shared_ready()
    return {
        "configured": row is not None,
        "provider": row.provider if row else llm_config.PROVIDER_LOCAL,
        "base_url": settings.model_local_base_url if ready else "",
        "chat_model": row.chat_model if row else settings.local_chat_model,
        "analysis_model": row.analysis_model if row else settings.local_analysis_model,
        "copilot_model": row.copilot_model if row else "",
        "max_tokens": row.max_tokens if row else min(settings.model_local_max_tokens, 32768),
        "timeout_seconds": row.timeout_seconds if row else settings.model_local_timeout_seconds,
        "local_available": ready,
        "anthropic_allowed": bool(settings.model_allow_commercial and settings.anthropic_api_key),
    }


def save(db: Session, user_id: uuid.UUID, payload) -> dict:
    settings = get_settings()
    if payload.provider == llm_config.PROVIDER_ANTHROPIC:
        if not settings.model_allow_commercial or not settings.anthropic_api_key:
            raise ValueError("Anthropic no está habilitado por el administrador.")
        endpoint = None
    else:
        _, endpoint = shared_gateway()
    fields = llm_config.validate(
        provider=payload.provider, base_url=endpoint, chat_model=payload.chat_model,
        analysis_model=payload.analysis_model, copilot_model=payload.copilot_model,
        max_tokens=payload.max_tokens, timeout_seconds=payload.timeout_seconds,
    )
    row = db.get(UserLLMPreference, user_id)
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
    # A preference update retires that account's old per-user encrypted secrets.
    row.lm_api_key_encrypted = None
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
    chat = row.chat_model if row else settings.local_chat_model
    analysis = row.analysis_model if row else settings.local_analysis_model
    copilot = row.copilot_model if row else ""
    return PersonalResolvedConfig(
        provider=selected, base_url=endpoint, chat_model=chat,
        analysis_model=analysis, copilot_model=copilot or chat,
        copilot_model_explicit=copilot, api_key=settings.model_local_api_key,
        max_tokens=row.max_tokens if row else min(settings.model_local_max_tokens, 32768),
        timeout_seconds=row.timeout_seconds if row else settings.model_local_timeout_seconds,
        label="Gateway compartido administrado", source="runtime",
        access_client_id=settings.model_local_cf_access_client_id,
        access_client_secret=settings.model_local_cf_access_client_secret,
        access_hostname=approved_host(),
    )

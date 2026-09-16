"""Per-account LLM choices. Never put credential plaintext in DB, audit or API responses.

The cloudflared connector token is deliberately NOT accepted here. Access
service credentials authenticate HTTP at Cloudflare, and the LM Studio API
key authenticates the same request at LM Studio.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
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
    cf_client_id_encrypted: Mapped[str | None] = mapped_column(Text)
    cf_client_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PersonalResolvedConfig(llm_config.ResolvedConfig):
    """Personal credentials travel to the provider factory only, never public_dict."""

    access_client_id: str = ""
    access_client_secret: str = ""
    access_hostname: str = ""


def _cipher() -> Fernet:
    key = os.environ.get("LLM_USER_CREDENTIALS_KEY", "").strip()
    if not key:
        raise RuntimeError("No se ha configurado el cifrado de credenciales en el backend.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise RuntimeError("La clave maestra de cifrado no es válida.") from exc


def _encrypt(value: str) -> str:
    return _cipher().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _cipher().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise RuntimeError("No se pueden descifrar las credenciales; se ha bloqueado la inferencia.") from exc


def _replace_secret(value: str | None, previous: str | None) -> str | None:
    # None = preserve; blank = remove; supplied value = rotate.
    if value is None:
        return previous
    if not value.strip():
        return None
    if len(value) > 8192 or "\r" in value or "\n" in value:
        raise ValueError("Formato de credencial no válido.")
    return _encrypt(value.strip())


def approved_host() -> str:
    settings = get_settings()
    host = settings.model_local_cf_access_host.strip().lower().rstrip(".")
    if not host:
        raise ValueError("El operador debe fijar MODEL_LOCAL_CF_ACCESS_HOST en el backend.")
    return host


def approved_endpoint(raw: str) -> str:
    """Host pinning blocks SSRF and exfiltration of *both* user credentials."""
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
        raise ValueError("Utiliza exclusivamente el endpoint HTTPS /v1 del host aprobado.")
    return url


def status(db: Session, user_id: uuid.UUID) -> dict:
    row = db.get(UserLLMPreference, user_id)
    settings = get_settings()
    if row is None:
        return {
            "configured": False, "provider": "anthropic", "base_url": settings.local_base_url or "",
            "chat_model": settings.anthropic_chat_model, "analysis_model": settings.anthropic_analysis_model,
            "copilot_model": "", "max_tokens": 4096, "timeout_seconds": 120,
            "lm_api_key_configured": False, "cf_client_id_configured": False,
            "cf_client_secret_configured": False, "anthropic_allowed": settings.model_allow_commercial,
        }
    return {
        "configured": True, "provider": row.provider, "base_url": row.base_url or "",
        "chat_model": row.chat_model, "analysis_model": row.analysis_model,
        "copilot_model": row.copilot_model, "max_tokens": row.max_tokens,
        "timeout_seconds": row.timeout_seconds,
        "lm_api_key_configured": bool(row.lm_api_key_encrypted),
        "cf_client_id_configured": bool(row.cf_client_id_encrypted),
        "cf_client_secret_configured": bool(row.cf_client_secret_encrypted),
        "anthropic_allowed": settings.model_allow_commercial,
    }


def save(db: Session, user_id: uuid.UUID, payload) -> dict:
    settings = get_settings()
    if payload.provider == llm_config.PROVIDER_ANTHROPIC and not settings.model_allow_commercial:
        raise ValueError("Anthropic está deshabilitado por la política del despliegue.")
    if payload.provider == llm_config.PROVIDER_ANTHROPIC and not settings.anthropic_api_key:
        raise ValueError("Anthropic no tiene una clave configurada en el servidor.")
    endpoint = approved_endpoint(payload.base_url) if payload.provider == llm_config.PROVIDER_LOCAL else None
    fields = llm_config.validate(
        provider=payload.provider, base_url=endpoint, chat_model=payload.chat_model,
        analysis_model=payload.analysis_model, copilot_model=payload.copilot_model,
        max_tokens=payload.max_tokens, timeout_seconds=payload.timeout_seconds,
    )
    row = db.get(UserLLMPreference, user_id)
    if row is None:
        row = UserLLMPreference(user_id=user_id, provider=fields["provider"],
                                chat_model=fields["chat_model"], analysis_model=fields["analysis_model"])
    # All saved credentials are encrypted even while Anthropic is selected.
    lm = _replace_secret(payload.lm_api_key, row.lm_api_key_encrypted)
    cf_id = _replace_secret(payload.cf_client_id, row.cf_client_id_encrypted)
    cf_secret = _replace_secret(payload.cf_client_secret, row.cf_client_secret_encrypted)
    if payload.provider == llm_config.PROVIDER_LOCAL and not all((lm, cf_id, cf_secret)):
        raise ValueError("LM Studio exige clave API, Client ID y Client Secret de Cloudflare Access.")
    row.provider = fields["provider"]
    row.base_url = fields["base_url"] if payload.provider == llm_config.PROVIDER_LOCAL else None
    row.chat_model = fields["chat_model"]
    row.analysis_model = fields["analysis_model"]
    row.copilot_model = fields["copilot_model"]
    row.max_tokens = fields["max_tokens"]
    row.timeout_seconds = fields["timeout_seconds"]
    row.lm_api_key_encrypted = lm
    row.cf_client_id_encrypted = cf_id
    row.cf_client_secret_encrypted = cf_secret
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    return status(db, user_id)


def resolve(db: Session, user_id: uuid.UUID) -> PersonalResolvedConfig:
    row = db.get(UserLLMPreference, user_id)
    if row is None:
        raise RuntimeError("Configura tu proveedor y credenciales personales antes de usar el modelo.")
    settings = get_settings()
    if row.provider == llm_config.PROVIDER_ANTHROPIC:
        if not settings.model_allow_commercial or not settings.anthropic_api_key:
            raise RuntimeError("Anthropic no está disponible para este despliegue.")
        return PersonalResolvedConfig(
            provider=row.provider, chat_model=row.chat_model, analysis_model=row.analysis_model,
            copilot_model=row.copilot_model or row.chat_model,
            copilot_model_explicit=row.copilot_model, api_key=settings.anthropic_api_key,
            max_tokens=row.max_tokens, timeout_seconds=row.timeout_seconds,
            label="Selección personal", source="runtime",
        )
    if row.provider != llm_config.PROVIDER_LOCAL or not all((row.lm_api_key_encrypted, row.cf_client_id_encrypted, row.cf_client_secret_encrypted)):
        raise RuntimeError("Faltan credenciales personales de LM Studio o Cloudflare Access.")
    url = approved_endpoint(row.base_url or "")
    return PersonalResolvedConfig(
        provider=row.provider, base_url=url, chat_model=row.chat_model,
        analysis_model=row.analysis_model, copilot_model=row.copilot_model or row.chat_model,
        copilot_model_explicit=row.copilot_model, api_key=_decrypt(row.lm_api_key_encrypted),
        max_tokens=row.max_tokens, timeout_seconds=row.timeout_seconds,
        label="Selección personal", source="runtime",
        access_client_id=_decrypt(row.cf_client_id_encrypted),
        access_client_secret=_decrypt(row.cf_client_secret_encrypted),
        access_hostname=approved_host(),
    )

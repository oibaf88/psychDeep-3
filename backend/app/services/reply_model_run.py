"""Canonical ``ModelRun`` rows for conversational replies (G3).

Agent 1 (patient chat) and Agent 3 (professional copilot) call the provider
directly, not through ``ModelGateway``. This module records one ``ModelRun``
per attempt:

- ``succeeded``: the reply passed ``output_validation`` and was shown.
- ``output_withheld``: the validator blocked the reply; the model text was
  replaced by server-owned copy (or, at alert levels 3/4, dropped in front
  of the fixed crisis copy).
- an existing failure status (``provider_error``, ``timeout``,
  ``configuration_error``, ``unavailable``, ``refused``, ``invalid_output``):
  the provider call raised before a reply could be validated.

``deployment_alias`` is ``direct-<provider>`` because these calls do not go
through ``ModelGateway``. Each row carries prompt and policy versions and a
SHA-256 of the prompt that was (or would have been) sent. It never carries
patient text, model text, prompts, endpoint URLs or the exception payload.
Recording is best-effort. A failure here is logged by exception type and
rolled back; it never changes what the user sees, and it never touches alert
levels, risk rules or crisis copy.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.output_validation import OutputValidation

logger = logging.getLogger(__name__)

STATUS_SUCCEEDED = "succeeded"
STATUS_OUTPUT_WITHHELD = "output_withheld"

# Already allowed by ck_model_run_status (foundation migration plus
# 20261017090000, which added output_withheld). Failure rows must use one of
# these. Do not invent a status: that needs a migration to widen the check.
FAILURE_STATUSES = frozenset({
    "provider_error",
    "timeout",
    "configuration_error",
    "unavailable",
    "refused",
    "invalid_output",
})

# Selected deployment could not be used. Same idea as ModelGateway's
# ModelUnavailable -> unavailable, without importing that graph.
_UNAVAILABLE_TYPES = frozenset({
    "ModelUnavailable",
    "LocalModelUnavailable",
    "LocalLlmAccessDenied",
})

# Fixed tokens this process raises. Compared, never stored.
_CONFIGURATION_SENTINELS = frozenset({
    "OPENAI_API_KEY_NOT_CONFIGURED",
    "LOCAL_ENDPOINT_HOST_NOT_APPROVED",
})


def input_hash(system_prompt: str, messages: list[dict[str, str]] | None) -> str:
    """SHA-256 of the prompt and turns sent; the text itself is never kept."""
    payload = {"system": system_prompt, "messages": messages or []}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def call_identity(provider: Any) -> tuple[str | None, str | None]:
    """Provider label and chat model, read off the object without calling it.

    Real adapters do not share one attribute for this, so the class name is
    the fallback. A stub may set ``provider_name`` instead. Returns None
    when the object does not say.
    """
    explicit = getattr(provider, "provider_name", None)
    provider_name = explicit.strip() if isinstance(explicit, str) else ""
    if not provider_name:
        names = {cls.__name__ for cls in type(provider).mro()}
        if "AnthropicProvider" in names:
            provider_name = "anthropic"
        elif "OpenAIProvider" in names and "OpenAICompatibleProvider" not in names:
            provider_name = "openai"
        elif "OpenAICompatibleProvider" in names:
            provider_name = "openai_compatible"
    model = (
        getattr(provider, "chat_model", None)
        or getattr(provider, "_chat_model", None)
        or getattr(provider, "copilot_model", None)
    )
    model_id = model.strip() if isinstance(model, str) else ""
    return (provider_name or None), (model_id or None)


def status_for_provider_failure(exc: BaseException) -> str:
    """Map a provider exception onto an existing ``ModelRun`` status.

    Prefers the provider's own ``safe_kind`` when that kind is already
    allowed. Otherwise the same split ``ModelGateway`` uses: timeout,
    unavailable, or ``provider_error``. The exception message is not part
    of the result.
    """
    kind = getattr(exc, "safe_kind", None)
    if isinstance(kind, str) and kind in FAILURE_STATUSES:
        return kind
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return "timeout"
    if type(exc).__name__ in _UNAVAILABLE_TYPES:
        return "unavailable"
    if type(exc) is RuntimeError and len(exc.args) == 1 and isinstance(exc.args[0], str):
        token = exc.args[0]
        if token == "empty_reply":
            return "invalid_output"
        if token in _CONFIGURATION_SENTINELS:
            return "configuration_error"
    return "provider_error"


def _clipped(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text[:limit]


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _persist(db: Session, row: Any, *, label: str):
    """Commit one row. On failure, log the exception type only and roll back."""
    try:
        db.add(row)
        db.commit()
        return row
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not record ModelRun for %s: %s", label, type(exc).__name__)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


def record_validated_reply(
    db: Session,
    *,
    check: OutputValidation,
    metadata: Any,
    purpose: str,
    audience: str,
    user_id: uuid.UUID | None,
    prompt_version: str,
    system_prompt: str,
    messages: list[dict[str, str]] | None,
    correlation_id: uuid.UUID | None,
):
    """Write the ``ModelRun`` for one validated reply. Returns the row or None."""
    from app.models_vnext import ModelRun

    try:
        provider = (getattr(metadata, "provider", None) or "unknown")[:48]
        model_id = (
            getattr(metadata, "response_model", None)
            or getattr(metadata, "requested_model", None)
            or "unknown"
        )[:192]
        row = ModelRun(
            user_id=user_id,
            purpose=purpose,
            audience=audience,
            # These calls do not go through ModelGateway, so there is no
            # approved deployment alias to name; say so explicitly.
            deployment_alias=f"direct-{provider}"[:96],
            provider_type=provider,
            model_id=model_id,
            model_version=getattr(metadata, "response_model", None),
            prompt_version=prompt_version,
            policy_version=get_settings().model_policy_version,
            input_hash=input_hash(system_prompt, messages),
            status=STATUS_OUTPUT_WITHHELD if check.blocked else STATUS_SUCCEEDED,
            correlation_id=correlation_id,
            latency_ms=getattr(metadata, "latency_ms", None),
            input_tokens=getattr(metadata, "input_tokens", None),
            output_tokens=getattr(metadata, "output_tokens", None),
            output_validator_version=check.validator_version,
            output_violation_codes=list(check.violations),
        )
    except Exception as exc:  # noqa: BLE001
        # Building the row failed (settings, hashing). Nothing was added.
        logger.error("Could not record ModelRun for validated %s reply: %s", purpose, type(exc).__name__)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None
    return _persist(db, row, label=f"validated {purpose} reply")


def record_provider_failure(
    db: Session,
    *,
    exc: BaseException,
    purpose: str,
    audience: str,
    user_id: uuid.UUID | None,
    prompt_version: str,
    system_prompt: str,
    messages: list[dict[str, str]] | None,
    correlation_id: uuid.UUID | None,
    provider: str | None = None,
    model_id: str | None = None,
):
    """Write the ``ModelRun`` for a provider call that raised.

    Returns the row, or None when the write fails. Never raises. The
    exception object is used only to choose an allowed status and, when the
    provider attached ``metadata``, the provider name and model id. Its
    message is not written and not logged.
    """
    from app.models_vnext import ModelRun

    try:
        metadata = getattr(exc, "metadata", None)
        provider_name = (
            _clipped(getattr(metadata, "provider", None), 48)
            or _clipped(provider, 48)
            or "unknown"
        )
        model_name = (
            _clipped(getattr(metadata, "response_model", None), 192)
            or _clipped(getattr(metadata, "requested_model", None), 192)
            or _clipped(model_id, 192)
            or "unknown"
        )
        row = ModelRun(
            user_id=user_id,
            purpose=purpose,
            audience=audience,
            deployment_alias=f"direct-{provider_name}"[:96],
            provider_type=provider_name,
            model_id=model_name,
            model_version=_clipped(getattr(metadata, "response_model", None), 192),
            prompt_version=prompt_version,
            policy_version=get_settings().model_policy_version,
            input_hash=input_hash(system_prompt, messages),
            status=status_for_provider_failure(exc),
            correlation_id=correlation_id,
            latency_ms=_optional_int(getattr(metadata, "latency_ms", None)),
            input_tokens=_optional_int(getattr(metadata, "input_tokens", None)),
            output_tokens=_optional_int(getattr(metadata, "output_tokens", None)),
            # Validation did not run. Null, not an empty violation list.
            output_validator_version=None,
            output_violation_codes=None,
        )
    except Exception as write_exc:  # noqa: BLE001
        logger.error("Could not record ModelRun for failed %s call: %s", purpose, type(write_exc).__name__)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None
    return _persist(db, row, label=f"failed {purpose} call")

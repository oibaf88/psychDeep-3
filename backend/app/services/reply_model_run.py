"""Canonical ``ModelRun`` rows for validated conversational replies (G3).

Agent 1 (patient chat) and Agent 3 (professional copilot) call the provider
directly, not through ``ModelGateway``, so until now they wrote no
``ModelRun`` at all and model governance could not count how often a reply
was withheld by output validation. This module records one ``ModelRun`` per
validated reply:

- ``succeeded``: the reply passed ``output_validation`` and was shown.
- ``output_withheld``: the validator blocked the reply; the model text was
  replaced by server-owned copy (or, at alert levels 3/4, dropped in front
  of the fixed crisis copy).

Each row carries the validator version and the rule codes. It never carries
patient or model text: the input is stored as a SHA-256 hash only, exactly
as ``ModelGateway`` does. Recording is best-effort. A failure here is logged
by exception type and rolled back; it never changes what the user sees, and
it never touches alert levels, risk rules or crisis copy.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.output_validation import OutputValidation

logger = logging.getLogger(__name__)

STATUS_SUCCEEDED = "succeeded"
STATUS_OUTPUT_WITHHELD = "output_withheld"


def input_hash(system_prompt: str, messages: list[dict[str, str]] | None) -> str:
    """SHA-256 of the prompt and turns sent; the text itself is never kept."""
    payload = {"system": system_prompt, "messages": messages or []}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
        db.add(row)
        db.commit()
        return row
    except Exception as exc:  # noqa: BLE001
        # The reply the user sees is already decided; only this row is lost.
        logger.error("Could not record ModelRun for validated %s reply: %s", purpose, type(exc).__name__)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None

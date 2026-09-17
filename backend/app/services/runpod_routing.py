"""Strict allowlist for the operator-owned Runpod inference endpoint.

Never infer credential ownership from a user-supplied hostname. The URL must
match MODEL_CLOUD_BASE_URL exactly, and that operator setting must match the
Runpod OpenAI-compatible API shape. The Runpod key stays in Render only.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit


_ENDPOINT_ID = re.compile(r"[A-Za-z0-9_-]+\Z")


def validated_runpod_url(raw: str) -> str:
    url = (raw or "").strip().rstrip("/")
    parsed = urlsplit(url)
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.runpod.ai"
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or len(parts) != 4
        or parts[0] != "v2"
        or not _ENDPOINT_ID.fullmatch(parts[1])
        or parts[2:] != ["openai", "v1"]
    ):
        raise RuntimeError("RUNPOD_ENDPOINT_INVALID")
    return url


def cloud_credentials_for(config, settings) -> str | None:
    """Return the Runpod key only for the exact approved endpoint and model IDs.

    None means this is not the operator-pinned cloud profile. Raises on bad
    cloud configuration so a local/Cloudflare credential is never substituted.
    Optional cloud profile may not exist in older settings/test fixtures.
    """
    raw = (getattr(settings, "model_cloud_base_url", "") or "").strip()
    if not raw:
        return None
    pinned = raw.rstrip("/")
    actual = (config.base_url or "").strip().rstrip("/")
    if actual != pinned:
        return None
    validated_runpod_url(pinned)
    key = settings.model_cloud_api_key.strip()
    if not key:
        raise RuntimeError("RUNPOD_CREDENTIAL_NOT_CONFIGURED")
    approved = {
        settings.model_cloud_chat_model.strip(),
        settings.model_cloud_analysis_model.strip() or settings.model_cloud_chat_model.strip(),
        settings.model_cloud_copilot_model.strip() or settings.model_cloud_chat_model.strip(),
    }
    approved.discard("")
    if not approved or any(
        value not in approved
        for value in (config.chat_model, config.analysis_model, config.copilot_model or config.chat_model)
    ):
        raise RuntimeError("RUNPOD_MODEL_NOT_APPROVED")
    return key

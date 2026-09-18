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
    """Return a cloud key only for the approved destination and model IDs.

    An unapproved api.runpod.ai destination must never fall through to the
    legacy local provider, even if Cloudflare Access is disabled. Missing
    cloud settings remain compatible with older local-only deployments.
    """
    raw = (getattr(settings, "model_cloud_base_url", "") or "").strip()
    pinned = raw.rstrip("/")
    actual = (config.base_url or "").strip().rstrip("/")

    # This check precedes the optional cloud-profile check: otherwise a
    # runtime override could send an LM Studio bearer to another Runpod ID.
    if urlsplit(actual).hostname == "api.runpod.ai" and (not pinned or actual != pinned):
        raise RuntimeError("RUNPOD_ENDPOINT_NOT_APPROVED")
    if not pinned or actual != pinned:
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

"""Cloudflare Access service-token authentication for the local model gateway.

These credentials are separate from the cloudflared connector token and the
LM Studio API token. They must never be sent to the browser or to an arbitrary
runtime-selected endpoint.
"""
from __future__ import annotations

from urllib.parse import urlparse

from app.services.llm.openai_compatible import OpenAICompatibleProvider


class CloudflareAccessOpenAICompatibleProvider(OpenAICompatibleProvider):
    """Send Access service credentials only to the explicitly approved HTTPS host."""

    def __init__(
        self,
        *,
        access_client_id: str,
        access_client_secret: str,
        access_hostname: str,
        **kwargs,
    ) -> None:
        hostname = access_hostname.strip().lower().rstrip(".")
        endpoint = urlparse(kwargs.get("base_url") or "")
        if (
            not access_client_id.strip()
            or not access_client_secret.strip()
            or not hostname
            or endpoint.scheme != "https"
            or endpoint.hostname != hostname
            or endpoint.username is not None
            or endpoint.password is not None
            or endpoint.port not in (None, 443)
        ):
            raise RuntimeError(
                "Cloudflare Access requiere credenciales completas y una URL HTTPS "
                "cuyo hostname coincida exactamente con MODEL_LOCAL_CF_ACCESS_HOST."
            )
        super().__init__(**kwargs)
        self._access_client_id = access_client_id.strip()
        self._access_client_secret = access_client_secret.strip()

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        headers["CF-Access-Client-Id"] = self._access_client_id
        headers["CF-Access-Client-Secret"] = self._access_client_secret
        return headers

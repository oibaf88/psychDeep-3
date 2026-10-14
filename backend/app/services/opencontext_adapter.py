"""Opt-in HTTP adapter for OpenContext.

This module intentionally does not wire itself into chat yet. It provides a
small, testable transport boundary for a staged rollout. Supabase remains the
clinical source of truth. Callers must perform the current consent check and
derive the OpenContext principal from authenticated server-side identity.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

logger = logging.getLogger("psychapp.opencontext")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        return None


@dataclass(frozen=True)
class OpenContextConfig:
    enabled: bool
    base_url: str
    token: str
    agent_id: str
    timeout_seconds: float = 5.0
    max_context_tokens: int = 1000

    @classmethod
    def from_env(cls) -> "OpenContextConfig":
        enabled = os.getenv("OPENCONTEXT_ENABLED", "false").strip().lower() == "true"
        base_url = os.getenv("OPENCONTEXT_BASE_URL", "").strip().rstrip("/")
        token = os.getenv("OPENCONTEXT_API_TOKEN", "")
        agent_id = os.getenv("OPENCONTEXT_AGENT_ID", "psychdeep-agent1").strip()
        try:
            timeout = max(0.5, min(float(os.getenv("OPENCONTEXT_TIMEOUT_SECONDS", "5")), 15.0))
        except ValueError:
            timeout = 5.0
        try:
            budget = max(0, min(int(os.getenv("OPENCONTEXT_MAX_CONTEXT_TOKENS", "1000")), 3000))
        except ValueError:
            budget = 1000
        return cls(enabled, base_url, token, agent_id, timeout, budget)

    def validate(self, *, allow_local_http: bool = False) -> None:
        if not self.enabled:
            return
        if not self.base_url or not self.token or not self.agent_id:
            raise ValueError("OpenContext enabled but required configuration is missing")
        parsed = urlsplit(self.base_url)
        allowed_local = allow_local_http and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not allowed_local:
            raise ValueError("OpenContext requires HTTPS outside explicit local development")
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Invalid OpenContext base URL")


class OpenContextClient:
    """Minimal HTTP client that checks HTTP and application-level outcomes."""

    def __init__(self, config: OpenContextConfig, *, allow_local_http: bool = False):
        config.validate(allow_local_http=allow_local_http)
        self.config = config
        self._opener = build_opener(_NoRedirect())

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "disabled": True}
        self.config.validate(allow_local_http=urlsplit(self.config.base_url).hostname in {"localhost", "127.0.0.1", "::1"})
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("OpenContext path must be an absolute API path")
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(
            self.config.base_url + path,
            data=body,
            headers={
                "Authorization": "Bearer " + self.config.token,
                "Accept": "application/json",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
            method=method,
        )
        try:
            with self._opener.open(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise RuntimeError("OpenContext response exceeded size limit")
                decoded = json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            # Do not log request headers, body, URL query data or exception content.
            logger.warning("OpenContext HTTP failure status=%s path=%s", exc.code, path)
            raise RuntimeError(f"OpenContext HTTP failure ({exc.code})") from None
        except (URLError, TimeoutError, OSError) as exc:
            logger.warning("OpenContext transport failure type=%s", type(exc).__name__)
            raise RuntimeError("OpenContext transport failure") from None
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("OpenContext invalid response type=%s", type(exc).__name__)
            raise RuntimeError("OpenContext returned invalid JSON") from None
        if not isinstance(decoded, dict) or decoded.get("ok") is False:
            raise RuntimeError("OpenContext returned an unsuccessful application result")
        return decoded

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def discover_tools(self) -> dict[str, Any]:
        return self._request("GET", "/api/tools?format=openai")

    def search(self, query: str, *, k: int = 5, budget_tokens: int | None = None) -> dict[str, Any]:
        if not query.strip():
            return {"ok": True, "hits": [], "rendered": ""}
        payload = {
            "query": query.strip(),
            "k": max(1, min(int(k), 8)),
            "budget_tokens": max(0, min(
                int(self.config.max_context_tokens if budget_tokens is None else budget_tokens),
                self.config.max_context_tokens,
            )),
        }
        return self._request("POST", "/api/search", payload)

    def ingest_interaction(
        self,
        *,
        session_id: str,
        event_id: str,
        messages: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a verbatim interaction envelope; caller must consent-gate.

        If the write times out, the outcome is uncertain. Reconcile via the
        raw-event read API before attempting a retry.
        """
        if not session_id.strip() or not event_id.strip():
            raise ValueError("session_id and event_id are required")
        if not messages or len(messages) > 10000:
            raise ValueError("messages must contain 1..10000 items")
        ids = [item.get("message_id") for item in messages]
        if any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids):
            raise ValueError("each message requires a unique message_id")
        envelope = {
            "agent_id": self.config.agent_id,
            "session_id": session_id,
            "event_id": event_id,
            "metadata": metadata or {},
            "messages": messages,
        }
        return self._request("POST", "/api/interactions", envelope)


def make_event_id() -> str:
    """Create a stable-format event identifier; persist it before a network write."""
    return str(uuid.uuid4())

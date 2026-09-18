#!/usr/bin/env python3
"""Preflight a Runpod vLLM endpoint with synthetic data only.

Never pass patient text or secrets as CLI arguments. Reads MODEL_CLOUD_* from
server-side environment and does not print the endpoint credential or prompt.
Exit 0 only after exact-model discovery and a successful chat completion.
"""
from __future__ import annotations

import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def check_url(value: str) -> str:
    raw = value.strip().rstrip("/")
    url = urlparse(raw)
    if url.scheme != "https" or url.username or url.password or url.query or url.fragment or url.port:
        raise ValueError("Runpod base URL must be HTTPS without userinfo, port, query or fragment")
    if url.hostname == "api.runpod.ai":
        if not re.fullmatch(r"/v2/[A-Za-z0-9_-]+/openai/v1", url.path):
            raise ValueError("Queue endpoint must end with /v2/ENDPOINT_ID/openai/v1")
    elif url.hostname and re.fullmatch(r"[A-Za-z0-9-]+\.api\.runpod\.ai", url.hostname):
        if url.path != "/v1":
            raise ValueError("Load-balancer endpoint must end with /v1")
    else:
        raise ValueError("This preflight only accepts official Runpod API hostnames")
    return raw


def request_json(url: str, key: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(
        url,
        data=data,
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json", "Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urlopen(req, timeout=90) as response:
        parsed = json.load(response)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object")
    return parsed


def main() -> int:
    try:
        base_url = check_url(os.environ.get("MODEL_CLOUD_BASE_URL", ""))
        key = os.environ.get("MODEL_CLOUD_API_KEY", "").strip()
        model = os.environ.get("MODEL_CLOUD_CHAT_MODEL", "").strip()
        analysis = os.environ.get("MODEL_CLOUD_ANALYSIS_MODEL", "").strip() or model
        if not key or not model or not analysis:
            raise ValueError("MODEL_CLOUD_API_KEY and cloud model IDs are required")
        listed = request_json(f"{base_url}/models", key)
        ids = {entry.get("id") for entry in listed.get("data", []) if isinstance(entry, dict)}
        if not {model, analysis}.issubset(ids):
            raise ValueError("The configured chat/analysis model IDs do not match /models")
        result = request_json(
            f"{base_url}/chat/completions", key,
            {"model": model, "messages": [
                {"role": "system", "content": "Synthetic connectivity test. Reply with OK only."},
                {"role": "user", "content": "OK"},
            ], "temperature": 0, "max_tokens": 16},
        )
        choices = result.get("choices") or []
        text = ((choices[0].get("message") or {}).get("content") or "") if choices and isinstance(choices[0], dict) else ""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Chat completion returned no text")
        print("PASS: authenticated model discovery and synthetic chat completion")
        print("NEXT: structured-output, Spanish-language, privacy, clinical safety and audit gates are still required")
        return 0
    except HTTPError as exc:
        print(f"FAIL: endpoint returned HTTP {exc.code}; no credentials logged", file=sys.stderr)
    except (URLError, TimeoutError):
        print("FAIL: endpoint connection or timeout; no credentials logged", file=sys.stderr)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        # Only messages generated in this module are emitted, never response bodies.
        print(f"FAIL: {type(exc).__name__}; verify URL, model IDs and endpoint readiness", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

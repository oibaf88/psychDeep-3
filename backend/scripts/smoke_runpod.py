"""Synthetic smoke test for a Runpod vLLM OpenAI-compatible endpoint.

Never send clinical data. Never print credentials, response bodies or prompts.
Required environment variables: MODEL_CLOUD_BASE_URL, MODEL_CLOUD_API_KEY,
MODEL_CLOUD_CHAT_MODEL. Invoke: python backend/scripts/smoke_runpod.py
"""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def validate_base_url(raw: str) -> str:
    url = raw.strip().rstrip("/")
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
        or not parts[1]
        or parts[2:] != ["openai", "v1"]
    ):
        raise ValueError("Expected https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1")
    return url


def request_json(url: str, api_key: str, payload: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers=headers, method="POST" if payload is not None else "GET")
    with urlopen(req, timeout=180) as response:
        return json.load(response)


def main() -> int:
    try:
        base = validate_base_url(os.environ.get("MODEL_CLOUD_BASE_URL", ""))
        key = os.environ.get("MODEL_CLOUD_API_KEY", "").strip()
        model = os.environ.get("MODEL_CLOUD_CHAT_MODEL", "").strip()
        if not key or not model:
            raise ValueError("MODEL_CLOUD_API_KEY and MODEL_CLOUD_CHAT_MODEL are required")
        catalog = request_json(f"{base}/models", key)
        model_ids = {entry.get("id") for entry in catalog.get("data", []) if isinstance(entry, dict)}
        if model not in model_ids:
            raise ValueError("Configured model not advertised by /models; check served model name")
        answer = request_json(
            f"{base}/chat/completions", key,
            {"model": model, "messages": [{"role": "user", "content": "Reply with exactly READY."}],
             "max_tokens": 32, "temperature": 0, "stream": False},
        )
        choices = answer.get("choices") or []
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Chat completion has no text")
        print("PASS: authenticated /models and synthetic chat returned a non-empty response")
        print("NOTE: structured JSON, streaming, clinical accuracy and privacy compliance NOT validated")
        return 0
    except (ValueError, HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        # Never echo URLs, headers, prompts or server bodies: they may contain secrets.
        print(f"FAIL: Runpod smoke test ({type(exc).__name__})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

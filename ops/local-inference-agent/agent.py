from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
from urllib.parse import urlencode

import httpx
import websockets
from dotenv import load_dotenv

load_dotenv()


API_URL = os.environ.get("PSYCHDEEP_API_URL", "https://psychdeep-api.onrender.com").rstrip("/")
SECRET = os.environ["PSYCHDEEP_LOCAL_BRIDGE_SECRET"].strip()
AGENT_ID = os.environ.get("PSYCHDEEP_LOCAL_AGENT_ID", "primary-windows").strip()
LOCAL_BASE_URL = os.environ.get("LOCAL_LLM_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")
LOCAL_API_KEY = os.environ.get("LOCAL_LLM_API_KEY", "").strip()
CHAT_MODEL = os.environ.get("LOCAL_LLM_CHAT_MODEL", "").strip()
ANALYSIS_MODEL = os.environ.get("LOCAL_LLM_ANALYSIS_MODEL", "").strip() or CHAT_MODEL
VERIFY_TLS = os.environ.get("PSYCHDEEP_VERIFY_TLS", "true").strip().lower() not in {"0", "false", "no"}


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(payload: dict) -> str:
    return hmac.new(SECRET.encode("utf-8"), canonical(payload), hashlib.sha256).hexdigest()


def auth_url() -> str:
    challenge = secrets.token_urlsafe(24)
    expires_at = int(time.time()) + 60
    signed = {"agent_id": AGENT_ID, "challenge": challenge, "expires_at": expires_at}
    query = urlencode(
        {
            "agent_id": AGENT_ID,
            "challenge": challenge,
            "expires_at": str(expires_at),
            "token": sign(signed),
        }
    )
    return f"{API_URL.replace('https://', 'wss://').replace('http://', 'ws://')}/local-bridge/connect?{query}"


def headers() -> dict[str, str]:
    result = {"Content-Type": "application/json"}
    if LOCAL_API_KEY:
        result["Authorization"] = f"Bearer {LOCAL_API_KEY}"
    return result


async def call_local_model(payload: dict) -> dict:
    kind = payload["kind"]
    model = payload["model"]
    if not model:
        raise RuntimeError("LOCAL_LLM_MODEL_NOT_CONFIGURED")

    if kind == "chat":
        body = {
            "model": model,
            "max_tokens": payload.get("max_tokens", 8192),
            "messages": [
                {"role": "system", "content": payload["system_prompt"]},
                *payload.get("messages", []),
            ],
        }
    elif kind == "structured":
        schema = payload["tool_schema"]
        body = {
            "model": model,
            "max_tokens": payload.get("max_tokens", 8192),
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        payload["system_prompt"]
                        + "\n\nDevuelve únicamente un objeto JSON válido que cumpla exactamente este esquema:\n"
                        + json.dumps(schema["input_schema"], ensure_ascii=False)
                    ),
                },
                {"role": "user", "content": payload["user_text"]},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.get("name", "structured_output"),
                    "schema": schema["input_schema"],
                    "strict": True,
                },
            },
        }
    else:
        raise RuntimeError("LOCAL_LLM_REQUEST_KIND_INVALID")

    timeout = httpx.Timeout(600, connect=10)
    async with httpx.AsyncClient(timeout=timeout, verify=VERIFY_TLS) as client:
        response = await client.post(f"{LOCAL_BASE_URL}/chat/completions", headers=headers(), json=body)

        if response.status_code in {400, 422} and kind == "structured":
            body.pop("response_format", None)
            body["messages"][0]["content"] += (
                "\nSin texto antes ni después del JSON."
            )
            response = await client.post(
                f"{LOCAL_BASE_URL}/chat/completions",
                headers=headers(),
                json=body,
            )

        response.raise_for_status()
        data = response.json()

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("LOCAL_LLM_EMPTY_RESPONSE")
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        content = "\n".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )

    if kind == "chat":
        return {
            "text": str(content).strip(),
            "model": data.get("model") or model,
            "usage": data.get("usage") or {},
            "metadata": {
                "input_tokens": (data.get("usage") or {}).get("prompt_tokens"),
                "output_tokens": (data.get("usage") or {}).get("completion_tokens"),
            },
        }

    text = str(content).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("LOCAL_LLM_INVALID_JSON") from None
        value = json.loads(text[start : end + 1])

    if not isinstance(value, dict):
        raise RuntimeError("LOCAL_LLM_INVALID_STRUCTURED_OUTPUT")

    return {
        "value": value,
        "model": data.get("model") or model,
        "usage": data.get("usage") or {},
    }


async def run() -> None:
    if len(SECRET) < 32:
        raise SystemExit("PSYCHDEEP_LOCAL_BRIDGE_SECRET debe tener al menos 32 caracteres.")
    if not CHAT_MODEL:
        raise SystemExit("LOCAL_LLM_CHAT_MODEL es obligatorio.")

    while True:
        try:
            url = auth_url()
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
                max_size=32 * 1024 * 1024,
            ) as websocket:
                print(f"[psychDeep] agente conectado: {AGENT_ID}")
                async for raw in websocket:
                    message = json.loads(raw)
                    if message.get("type") != "inference_request":
                        continue

                    request_id = message["request_id"]
                    payload = message["payload"]
                    signed_request = {
                        "type": "inference_request",
                        "request_id": request_id,
                        "payload": payload,
                    }
                    if not hmac.compare_digest(
                        sign(signed_request),
                        message.get("signature", ""),
                    ):
                        print("[psychDeep] solicitud rechazada: firma no válida")
                        continue

                    started = time.perf_counter()
                    try:
                        result = await call_local_model(payload)
                    except Exception as exc:  # noqa: BLE001
                        result = {
                            "error": "LOCAL_INFERENCE_FAILED",
                            "error_type": type(exc).__name__,
                        }
                    result["elapsed_ms"] = round((time.perf_counter() - started) * 1000)

                    response = {
                        "type": "inference_result",
                        "request_id": request_id,
                        "result": result,
                    }
                    response["signature"] = sign(response)
                    await websocket.send(json.dumps(response, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            print(f"[psychDeep] desconectado: {type(exc).__name__}; reconectando en 5 s")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run())

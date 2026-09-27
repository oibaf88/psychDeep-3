"""First-party OpenAI Responses API adapter for PsychDeep."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.services.llm.base import (
    ChatResult,
    LLMProvider,
    ProviderMetadata,
    StructuredAnalysisError,
    StructuredAnalysisResult,
)

OPENAI_API_BASE_URL = "https://api.openai.com"
OPENAI_RESPONSES_URL = f"{OPENAI_API_BASE_URL}/v1/responses"

_UNSUPPORTED_SCHEMA_KEYS = {
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf", "minLength", "maxLength", "minItems", "maxItems", "pattern",
    "default",
}


def _to_strict_schema(node: Any) -> Any:
    if isinstance(node, list):
        return [_to_strict_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    converted = {
        key: _to_strict_schema(value)
        for key, value in node.items()
        if key not in _UNSUPPORTED_SCHEMA_KEYS
    }
    if converted.get("type") == "object" and "properties" in converted:
        converted["properties"] = {
            key: _to_strict_schema(value)
            for key, value in converted["properties"].items()
        }
        converted["required"] = list(converted["properties"].keys())
        converted["additionalProperties"] = False
    return converted


def _extract_text(body: dict[str, Any]) -> str:
    direct = body.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    texts: list[str] = []
    for item in body.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for part in item.get("content", []) or []:
            if isinstance(part, dict) and part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str):
                    texts.append(text)
    return "\n".join(texts).strip()


def _usage_value(usage: Any, name: str) -> int | None:
    if isinstance(usage, dict):
        value = usage.get(name)
    else:
        value = getattr(usage, name, None)
    return int(value) if isinstance(value, (int, float)) else None


class OpenAIProvider(LLMProvider):
    """OpenAI's Responses API behind the same provider contract as Claude."""

    def __init__(
        self,
        *,
        chat_model: str,
        analysis_model: str,
        copilot_model: str | None = None,
        api_key: str | None = None,
        max_tokens: int = 8192,
        timeout_seconds: float = 120,
        chat_effort: str = "medium",
        analysis_effort: str = "high",
        usage_recorder: Callable[..., None] | None = None,
    ):
        from app.config import get_settings

        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._chat_model = chat_model
        self._analysis_model = analysis_model
        self._copilot_model = copilot_model or chat_model
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds
        self._chat_effort = chat_effort
        self._analysis_effort = analysis_effort
        self._usage_recorder = usage_recorder

    def _require_key(self) -> str:
        if not self._api_key.strip():
            raise StructuredAnalysisError(
                "configuration_error",
                error_code="api_key_not_configured",
                metadata=ProviderMetadata(
                    provider="openai",
                    requested_model=self._chat_model,
                    base_url=OPENAI_API_BASE_URL,
                ),
            )
        return self._api_key

    @staticmethod
    def _metadata(body: dict[str, Any], headers: httpx.Headers, requested_model: str, latency_ms: int) -> ProviderMetadata:
        usage = body.get("usage") or {}
        details = usage.get("output_tokens_details") if isinstance(usage, dict) else None
        return ProviderMetadata(
            provider="openai",
            requested_model=requested_model,
            response_model=body.get("model") if isinstance(body.get("model"), str) else None,
            base_url=OPENAI_API_BASE_URL,
            message_id=body.get("id") if isinstance(body.get("id"), str) else None,
            request_id=headers.get("x-request-id"),
            stop_reason=body.get("status") if isinstance(body.get("status"), str) else None,
            input_tokens=_usage_value(usage, "input_tokens"),
            output_tokens=_usage_value(usage, "output_tokens"),
            thinking_tokens=_usage_value(details, "reasoning_tokens"),
            latency_ms=latency_ms,
        )

    def _record(self, **kwargs) -> None:
        if self._usage_recorder is not None:
            self._usage_recorder(**kwargs)

    @property
    def copilot_model(self) -> str:
        return self._copilot_model

    @property
    def copilot_effort(self) -> str:
        return self._chat_effort

    @staticmethod
    def _input(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        return [
            {
                "role": message["role"],
                "content": [{"type": "input_text", "text": message["content"]}],
            }
            for message in messages
        ]

    def _post(self, payload: dict[str, Any]) -> tuple[dict[str, Any], httpx.Headers, int]:
        api_key = self._require_key()
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=self._timeout_seconds, follow_redirects=False) as client:
                response = client.post(
                    OPENAI_RESPONSES_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException:
            raise StructuredAnalysisError("timeout", error_code="timeout") from None
        except httpx.HTTPError:
            raise StructuredAnalysisError("provider_error", error_code="network_error") from None

        latency_ms = round((time.perf_counter() - started) * 1000)
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.is_error:
            status = response.status_code
            raise StructuredAnalysisError(
                "configuration_error" if status in (400, 401, 403, 404) else "provider_error",
                error_code=f"http_{status}",
                http_status=status,
            )
        if not isinstance(body, dict):
            raise StructuredAnalysisError("provider_error", error_code="invalid_provider_response")
        return body, response.headers, latency_ms

    def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        *,
        model: str | None = None,
        effort: str | None = None,
    ) -> ChatResult:
        requested_model = model or self._chat_model
        token_budget = max_tokens or self._max_tokens
        effective_effort = effort or self._chat_effort
        payload: dict[str, Any] = {
            "model": requested_model,
            "instructions": system_prompt,
            "input": self._input(messages),
            "max_output_tokens": token_budget,
            "store": False,
        }
        if effective_effort:
            payload["reasoning"] = {"effort": effective_effort}

        started = time.perf_counter()
        try:
            body, headers, latency_ms = self._post(payload)
        except StructuredAnalysisError as exc:
            metadata = ProviderMetadata(
                provider="openai",
                requested_model=requested_model,
                base_url=OPENAI_API_BASE_URL,
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
            self._record(
                call_kind="chat",
                metadata=metadata,
                status="failed",
                effort=effective_effort,
                max_tokens=token_budget,
                system_chars=len(system_prompt),
                message_chars=sum(len(m.get("content") or "") for m in messages),
                schema_chars=0,
                error_kind=exc.error_code or exc.safe_kind,
            )
            exc.metadata = metadata
            raise

        metadata = self._metadata(body, headers, requested_model, latency_ms)
        text = _extract_text(body)
        self._record(
            call_kind="chat",
            metadata=metadata,
            status="succeeded",
            effort=effective_effort,
            max_tokens=token_budget,
            system_chars=len(system_prompt),
            message_chars=sum(len(m.get("content") or "") for m in messages),
            schema_chars=0,
        )
        if not text:
            raise StructuredAnalysisError("invalid_output", metadata=metadata, error_code="empty_output")
        return ChatResult(text=text, metadata=metadata)

    def analyze_structured(
        self,
        system_prompt: str,
        user_text: str,
        tool_schema: dict[str, Any],
        *,
        model: str | None = None,
        effort: str | None = None,
        max_tokens: int | None = None,
    ) -> StructuredAnalysisResult:
        requested_model = model or self._analysis_model
        token_budget = max_tokens or self._max_tokens
        effective_effort = effort or self._analysis_effort
        schema = _to_strict_schema(tool_schema["input_schema"])
        schema_chars = len(json.dumps(schema, ensure_ascii=False, separators=(",", ":")))
        payload: dict[str, Any] = {
            "model": requested_model,
            "instructions": system_prompt,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": user_text}]}],
            "max_output_tokens": token_budget,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": tool_schema.get("name", "structured_result"),
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        if effective_effort:
            payload["reasoning"] = {"effort": effective_effort}

        started = time.perf_counter()
        try:
            body, headers, latency_ms = self._post(payload)
        except StructuredAnalysisError as exc:
            metadata = ProviderMetadata(
                provider="openai",
                requested_model=requested_model,
                base_url=OPENAI_API_BASE_URL,
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
            self._record(
                call_kind="structured_analysis",
                metadata=metadata,
                status="failed",
                effort=effective_effort,
                max_tokens=token_budget,
                system_chars=len(system_prompt),
                message_chars=len(user_text),
                schema_chars=schema_chars,
                error_kind=exc.error_code or exc.safe_kind,
            )
            exc.metadata = metadata
            raise

        metadata = self._metadata(body, headers, requested_model, latency_ms)
        text = _extract_text(body)
        self._record(
            call_kind="structured_analysis",
            metadata=metadata,
            status="succeeded",
            effort=effective_effort,
            max_tokens=token_budget,
            system_chars=len(system_prompt),
            message_chars=len(user_text),
            schema_chars=schema_chars,
        )
        if not text:
            raise StructuredAnalysisError("invalid_output", metadata=metadata, error_code="empty_output")
        try:
            value = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            raise StructuredAnalysisError("invalid_output", metadata=metadata, error_code="invalid_json") from None
        if not isinstance(value, dict):
            raise StructuredAnalysisError("invalid_output", metadata=metadata, error_code="invalid_json_object")
        return StructuredAnalysisResult(value=value, metadata=metadata)

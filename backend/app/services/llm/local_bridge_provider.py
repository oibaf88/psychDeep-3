from __future__ import annotations

import time
from typing import Any

from app.services.llm.base import (
    ChatResult,
    LLMProvider,
    ProviderMetadata,
    StructuredAnalysisResult,
)
from app.services.local_inference_bridge import get_local_inference_bridge


class LocalBridgeProvider(LLMProvider):
    """LLMProvider adapter backed by the authenticated outbound local agent."""

    def __init__(
        self,
        *,
        chat_model: str,
        analysis_model: str,
        copilot_model: str,
        max_tokens: int,
        timeout_seconds: float,
        agent_id: str,
    ) -> None:
        self.chat_model = chat_model
        self.analysis_model = analysis_model
        self.copilot_model = copilot_model or chat_model
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.agent_id = agent_id

    def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        *,
        model: str | None = None,
        effort: str | None = None,
    ) -> ChatResult:
        selected_model = model or self.chat_model
        started = time.perf_counter()
        response = get_local_inference_bridge().submit_sync(
            request={
                "kind": "chat",
                "model": selected_model,
                "system_prompt": system_prompt,
                "messages": messages,
                "max_tokens": max_tokens or self.max_tokens,
            },
            agent_id=self.agent_id,
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        metadata = response.get("metadata") or {}
        usage = response.get("usage") or {}

        return ChatResult(
            text=str(response.get("text") or ""),
            metadata=ProviderMetadata(
                provider="local-bridge",
                requested_model=selected_model,
                response_model=response.get("model") or selected_model,
                input_tokens=metadata.get("input_tokens") or usage.get("prompt_tokens"),
                output_tokens=metadata.get("output_tokens") or usage.get("completion_tokens"),
                latency_ms=elapsed,
            ),
        )

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
        selected_model = model or self.analysis_model
        started = time.perf_counter()
        response = get_local_inference_bridge().submit_sync(
            request={
                "kind": "structured",
                "model": selected_model,
                "system_prompt": system_prompt,
                "user_text": user_text,
                "tool_schema": tool_schema,
                "max_tokens": max_tokens or self.max_tokens,
            },
            agent_id=self.agent_id,
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        usage = response.get("usage") or {}

        return StructuredAnalysisResult(
            value=response["value"],
            metadata=ProviderMetadata(
                provider="local-bridge",
                requested_model=selected_model,
                response_model=response.get("model") or selected_model,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                latency_ms=elapsed,
            ),
        )

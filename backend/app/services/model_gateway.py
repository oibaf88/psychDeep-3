"""Provider-neutral Model Gateway for PsychDeep vNext.

The clinical domain chooses a stable deployment alias; only this module knows
how that alias maps to a provider endpoint. There is deliberately no
primary/fallback chain: an unavailable approved deployment fails closed to the
caller's structured/static fallback and never moves PHI to another provider.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.llm import AnthropicProvider, OpenAICompatibleProvider
from app.services.llm.base import ChatResult, LLMProvider, StructuredAnalysisResult

logger = logging.getLogger("psychapp.model_gateway")

LOCAL_TUNNEL = "local-tunnel"
CLOUD_TUNED = "cloud-tuned"
COMMERCIAL_APPROVED = "commercial-approved"
APPROVED_ALIASES = {LOCAL_TUNNEL, CLOUD_TUNED, COMMERCIAL_APPROVED, "mobile-local"}


class ModelGatewayError(RuntimeError):
    pass


class ModelUnavailable(ModelGatewayError):
    """The selected deployment cannot serve the request safely."""


@dataclass(frozen=True)
class Deployment:
    alias: str
    adapter: Literal["openai_compatible", "managed_cloud", "mobile_local"]
    base_url: str | None
    api_key: str
    chat_model: str
    analysis_model: str
    copilot_model: str
    timeout_seconds: int
    max_tokens: int
    policy_version: str
    data_handling_classification: str

    def public_dict(self) -> dict[str, Any]:
        return {
            "alias": self.alias,
            "adapter": self.adapter,
            "chat_model": self.chat_model,
            "analysis_model": self.analysis_model,
            "copilot_model": self.copilot_model,
            "timeout_seconds": self.timeout_seconds,
            "policy_version": self.policy_version,
            "data_handling_classification": self.data_handling_classification,
            "configured": self.configured,
        }

    @property
    def configured(self) -> bool:
        if self.alias == COMMERCIAL_APPROVED:
            return bool(self.api_key and self.chat_model and self.analysis_model)
        return bool(self.base_url and self.chat_model and self.analysis_model)


@dataclass(frozen=True)
class GenerateRequest:
    system_prompt: str
    messages: list[dict[str, str]]
    purpose: str
    audience: str
    model_role: Literal["chat", "copilot"] = "chat"
    user_id: uuid.UUID | None = None
    correlation_id: uuid.UUID | None = None
    prompt_version: str = "unspecified"
    output_schema: str | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class GatewayChatResult:
    result: ChatResult
    model_run_id: uuid.UUID | None


@dataclass(frozen=True)
class GatewayStructuredResult:
    result: StructuredAnalysisResult
    model_run_id: uuid.UUID | None


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_private_host(host: str) -> bool:
    normalized = (host or "").strip().lower().rstrip(".")
    if normalized in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal"}:
        return True
    if normalized.endswith((".local", ".internal")):
        return True
    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)


def _normalise_openai_base_url(raw: str) -> str:
    url = (raw or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith("/chat/completions"):
        url = url[: -len("/chat/completions")]
    if url.endswith("/api/v1/chat"):
        url = url[: -len("/api/v1/chat")] + "/v1"
    elif url.endswith("/api/v1"):
        url = url[: -len("/api/v1")] + "/v1"
    parsed = urlparse(url)
    if not parsed.path.rstrip("/"):
        url = f"{url}/v1"
    return url


def _validate_endpoint(base_url: str, *, production: bool) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ModelUnavailable("MODEL_ENDPOINT_INVALID")
    if production:
        if parsed.scheme != "https":
            raise ModelUnavailable("MODEL_ENDPOINT_REQUIRES_HTTPS")
        if _is_private_host(parsed.hostname):
            raise ModelUnavailable("MODEL_ENDPOINT_PRIVATE_FROM_CLOUD")


class ModelGateway:
    def __init__(self, alias: str | None = None):
        self.settings = get_settings()
        self.alias = (alias or self.settings.model_deployment_alias).strip()
        if self.alias not in APPROVED_ALIASES:
            raise ModelUnavailable("MODEL_DEPLOYMENT_NOT_APPROVED")
        if self.alias == COMMERCIAL_APPROVED and not self.settings.model_allow_commercial:
            raise ModelUnavailable("COMMERCIAL_MODEL_NOT_APPROVED")

    def deployment(self) -> Deployment:
        s = self.settings
        if self.alias == LOCAL_TUNNEL:
            return Deployment(
                alias=LOCAL_TUNNEL,
                adapter="openai_compatible",
                base_url=_normalise_openai_base_url(s.local_base_url),
                api_key=s.local_api_key,
                chat_model=s.local_chat_model,
                analysis_model=s.local_analysis_model,
                copilot_model=s.local_copilot_model,
                timeout_seconds=s.model_local_timeout_seconds or s.llm_openai_compatible_timeout_seconds,
                max_tokens=s.model_local_max_tokens or s.llm_openai_compatible_max_tokens,
                policy_version=s.model_policy_version,
                data_handling_classification="clinical_data_private_tunnel",
            )
        if self.alias == "mobile-local":
            return Deployment(
                alias="mobile-local",
                adapter="mobile_local",
                base_url=None,
                api_key="",
                chat_model="device-reported",
                analysis_model="device-reported",
                copilot_model="device-reported",
                timeout_seconds=30,
                max_tokens=8192,
                policy_version=s.model_policy_version,
                data_handling_classification="clinical_data_device_local",
            )
        if self.alias == CLOUD_TUNED:
            chat = s.model_cloud_chat_model.strip()
            analysis = s.model_cloud_analysis_model.strip() or chat
            copilot = s.model_cloud_copilot_model.strip() or chat
            return Deployment(
                alias=CLOUD_TUNED,
                adapter="managed_cloud",
                base_url=_normalise_openai_base_url(s.model_cloud_base_url),
                api_key=s.model_cloud_api_key,
                chat_model=chat,
                analysis_model=analysis,
                copilot_model=copilot,
                timeout_seconds=s.model_cloud_timeout_seconds,
                max_tokens=s.model_cloud_max_tokens,
                policy_version=s.model_policy_version,
                data_handling_classification="clinical_data_managed_private",
            )
        return Deployment(
            alias=COMMERCIAL_APPROVED,
            adapter="managed_cloud",
            base_url=None,
            api_key=s.anthropic_api_key,
            chat_model=s.anthropic_chat_model,
            analysis_model=s.anthropic_analysis_model,
            copilot_model=s.copilot_model,
            timeout_seconds=s.model_cloud_timeout_seconds,
            max_tokens=s.anthropic_max_tokens,
            policy_version=s.model_policy_version,
            data_handling_classification="clinical_data_approved_commercial",
        )

    def provider(self) -> LLMProvider:
        d = self.deployment()
        if d.alias == "mobile-local":
            raise ModelUnavailable("MOBILE_LOCAL_REQUIRES_DEVICE_INGEST")
        if not d.configured:
            raise ModelUnavailable("MODEL_UNAVAILABLE")
        if d.alias == COMMERCIAL_APPROVED:
            from app.services.llm_usage import record_usage_safely

            return AnthropicProvider(
                chat_model=d.chat_model,
                analysis_model=d.analysis_model,
                copilot_model=d.copilot_model,
                max_tokens=d.max_tokens,
                usage_recorder=record_usage_safely,
            )
        assert d.base_url is not None
        _validate_endpoint(d.base_url, production=self.settings.is_production)
        return OpenAICompatibleProvider(
            base_url=d.base_url,
            chat_model=d.chat_model,
            analysis_model=d.analysis_model,
            copilot_model=d.copilot_model,
            api_key=d.api_key,
            max_tokens=d.max_tokens,
            timeout_seconds=float(d.timeout_seconds),
        )

    def _start_run(
        self,
        db: Session | None,
        *,
        user_id: uuid.UUID | None,
        purpose: str,
        audience: str,
        input_hash: str,
        prompt_version: str,
        output_schema: str | None,
        correlation_id: uuid.UUID | None,
        model_role: str,
    ):
        if db is None:
            return None
        from app.models_vnext import ModelRun

        d = self.deployment()
        model_id = d.analysis_model if model_role == "analysis" else (d.copilot_model if model_role == "copilot" else d.chat_model)
        row = ModelRun(
            user_id=user_id,
            purpose=purpose,
            audience=audience,
            deployment_alias=d.alias,
            provider_type=d.adapter,
            model_id=model_id,
            prompt_version=prompt_version,
            policy_version=d.policy_version,
            input_hash=input_hash,
            output_schema=output_schema,
            status="started",
            correlation_id=correlation_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def _finish_run(db: Session | None, row, *, result=None, status: str = "succeeded", latency_ms: int | None = None) -> None:
        if db is None or row is None:
            return
        row.status = status
        row.latency_ms = latency_ms
        if result is not None:
            metadata = result.metadata
            row.model_version = metadata.response_model
            row.input_tokens = metadata.input_tokens
            row.output_tokens = metadata.output_tokens
            if metadata.latency_ms is not None:
                row.latency_ms = metadata.latency_ms
        db.add(row)
        db.commit()

    def generate(self, request: GenerateRequest, *, db: Session | None = None) -> GatewayChatResult:
        payload_hash = _hash_payload({"system": request.system_prompt, "messages": request.messages})
        run = self._start_run(
            db,
            user_id=request.user_id,
            purpose=request.purpose,
            audience=request.audience,
            input_hash=payload_hash,
            prompt_version=request.prompt_version,
            output_schema=request.output_schema,
            correlation_id=request.correlation_id,
            model_role=request.model_role,
        )
        started = time.perf_counter()
        try:
            provider = self.provider()
            d = self.deployment()
            model = d.copilot_model if request.model_role == "copilot" else d.chat_model
            result = provider.chat(
                request.system_prompt,
                request.messages,
                max_tokens=request.max_tokens,
                model=model,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = int((time.perf_counter() - started) * 1000)
            status = "unavailable" if isinstance(exc, ModelUnavailable) else ("timeout" if isinstance(exc, (TimeoutError, httpx.TimeoutException)) else "provider_error")
            self._finish_run(db, run, status=status, latency_ms=elapsed)
            if isinstance(exc, ModelGatewayError):
                raise
            raise ModelUnavailable("MODEL_UNAVAILABLE") from exc
        self._finish_run(db, run, result=result, latency_ms=int((time.perf_counter() - started) * 1000))
        return GatewayChatResult(result=result, model_run_id=getattr(run, "id", None))

    def analyze_structured(
        self,
        *,
        system_prompt: str,
        user_text: str,
        tool_schema: dict[str, Any],
        purpose: str,
        user_id: uuid.UUID | None,
        correlation_id: uuid.UUID | None,
        prompt_version: str,
        schema_version: str,
        db: Session | None = None,
    ) -> GatewayStructuredResult:
        payload_hash = _hash_payload({"system": system_prompt, "text": user_text, "schema": tool_schema})
        run = self._start_run(
            db,
            user_id=user_id,
            purpose=purpose,
            audience="system",
            input_hash=payload_hash,
            prompt_version=prompt_version,
            output_schema=schema_version,
            correlation_id=correlation_id,
            model_role="analysis",
        )
        started = time.perf_counter()
        try:
            provider = self.provider()
            d = self.deployment()
            result = provider.analyze_structured(
                system_prompt,
                user_text,
                tool_schema,
                model=d.analysis_model,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = int((time.perf_counter() - started) * 1000)
            status = "unavailable" if isinstance(exc, ModelUnavailable) else ("timeout" if isinstance(exc, (TimeoutError, httpx.TimeoutException)) else "provider_error")
            self._finish_run(db, run, status=status, latency_ms=elapsed)
            if isinstance(exc, ModelGatewayError):
                raise
            raise ModelUnavailable("MODEL_UNAVAILABLE") from exc
        self._finish_run(db, run, result=result, latency_ms=int((time.perf_counter() - started) * 1000))
        return GatewayStructuredResult(result=result, model_run_id=getattr(run, "id", None))

    def health(self, deployment_alias: str | None = None) -> dict[str, Any]:
        gateway = self if deployment_alias is None or deployment_alias == self.alias else ModelGateway(deployment_alias)
        d = gateway.deployment()
        base = d.public_dict()
        if not d.configured:
            return {**base, "status": "unavailable", "reason": "not_configured"}
        if d.alias == COMMERCIAL_APPROVED:
            return {**base, "status": "configured"}
        assert d.base_url is not None
        try:
            _validate_endpoint(d.base_url, production=gateway.settings.is_production)
            headers = {"Authorization": f"Bearer {d.api_key}"} if d.api_key else {}
            with httpx.Client(timeout=min(float(d.timeout_seconds), 8.0), follow_redirects=False) as client:
                response = client.get(d.base_url.rstrip("/") + "/models", headers=headers)
            if response.status_code < 500:
                return {**base, "status": "available" if response.is_success else "degraded", "http_status": response.status_code}
            return {**base, "status": "unavailable", "http_status": response.status_code}
        except Exception as exc:  # noqa: BLE001
            logger.info("Model health check failed safely: %s", type(exc).__name__)
            return {**base, "status": "unavailable", "reason": type(exc).__name__}


def get_model_gateway(alias: str | None = None) -> ModelGateway:
    return ModelGateway(alias)

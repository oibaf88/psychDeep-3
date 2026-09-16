"""Low-level LLM provider adapters.

Application/domain code obtains the active provider through the audited runtime
selection layer. The deployment still supplies endpoint secrets and the
deterministic safety path remains independent from the selected model.
"""
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.base import (
    ChatResult,
    LLMProvider,
    ProviderMetadata,
    StructuredAnalysisError,
    StructuredAnalysisResult,
)
from app.services.llm.cloudflare_access import CloudflareAccessOpenAICompatibleProvider
from app.services.llm.openai_compatible import OpenAICompatibleProvider

__all__ = [
    "ChatResult",
    "LLMProvider",
    "ProviderMetadata",
    "StructuredAnalysisError",
    "StructuredAnalysisResult",
    "AnthropicProvider",
    "OpenAICompatibleProvider",
    "CloudflareAccessOpenAICompatibleProvider",
    "get_llm_provider",
    "build_provider",
]


def build_provider(config) -> LLMProvider:
    """Construct the concrete adapter for one already-resolved configuration."""
    from app.services import llm_config

    if config.provider == llm_config.PROVIDER_LOCAL:
        kwargs = dict(
            base_url=config.base_url or "",
            chat_model=config.chat_model,
            analysis_model=config.analysis_model,
            copilot_model=config.copilot_model,
            api_key=config.api_key,
            max_tokens=config.max_tokens,
            timeout_seconds=float(config.timeout_seconds),
        )
        settings = llm_config.get_settings()
        access = {
            "access_client_id": getattr(settings, "model_local_cf_access_client_id", ""),
            "access_client_secret": getattr(settings, "model_local_cf_access_client_secret", ""),
            "access_hostname": getattr(settings, "model_local_cf_access_host", ""),
        }
        access_required = getattr(settings, "model_local_cf_access_required", False)
        if access_required or any(value.strip() for value in access.values()):
            if not all(value.strip() for value in access.values()):
                raise RuntimeError(
                    "Cloudflare Access es obligatorio o está configurado parcialmente: "
                    "revisa MODEL_LOCAL_CF_ACCESS_CLIENT_ID, MODEL_LOCAL_CF_ACCESS_CLIENT_SECRET "
                    "y MODEL_LOCAL_CF_ACCESS_HOST en el backend."
                )
            # Access handles the public endpoint authentication. The cloudflared
            # connector token is never an HTTP credential, and a legacy LM Studio
            # bearer token must not be forwarded in this mode.
            kwargs["api_key"] = ""
            return CloudflareAccessOpenAICompatibleProvider(**kwargs, **access)
        return OpenAICompatibleProvider(**kwargs)
    if config.provider == llm_config.PROVIDER_ANTHROPIC:
        from app.services.llm_usage import record_usage_safely

        return AnthropicProvider(
            chat_model=config.chat_model,
            analysis_model=config.analysis_model,
            copilot_model=config.copilot_model,
            max_tokens=config.explicit_max_tokens,
            usage_recorder=record_usage_safely,
        )
    raise RuntimeError("Proveedor LLM no admitido.")


def get_llm_provider(db=None) -> LLMProvider:
    """Return the provider selected for this request.

    When ``LLM_ALLOW_RUNTIME_OVERRIDE`` is enabled, an ``admin_clinical`` can
    select Anthropic or the approved OpenAI-compatible local/tunnel endpoint
    without redeploying. The selection is read from the audited
    ``llm_endpoint_configs`` history; endpoint credentials still come from
    server-side configuration unless the legacy local-token field was
    deliberately populated.
    """
    from app.services import llm_config

    return build_provider(llm_config.resolve(db))

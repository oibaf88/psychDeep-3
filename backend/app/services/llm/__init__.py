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
from app.services.llm.openai_compatible import OpenAICompatibleProvider

__all__ = [
    "ChatResult",
    "LLMProvider",
    "ProviderMetadata",
    "StructuredAnalysisError",
    "StructuredAnalysisResult",
    "AnthropicProvider",
    "OpenAICompatibleProvider",
    "get_llm_provider",
    "build_provider",
]


def build_provider(config) -> LLMProvider:
    """Construct the concrete adapter for one already-resolved configuration."""
    from app.services import llm_config

    if config.provider == llm_config.PROVIDER_LOCAL:
        return OpenAICompatibleProvider(
            base_url=config.base_url or "",
            chat_model=config.chat_model,
            analysis_model=config.analysis_model,
            copilot_model=config.copilot_model,
            api_key=config.api_key,
            max_tokens=config.max_tokens,
            timeout_seconds=float(config.timeout_seconds),
        )
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

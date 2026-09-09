"""Gemma 2 local provider factory with Claude as a server-keyed alternative."""
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
    """Construct the provider one resolved configuration describes."""
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
    """Return the provider currently in force."""
    from app.services import llm_config

    return build_provider(llm_config.resolve(db))

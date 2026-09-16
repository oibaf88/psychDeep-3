"""Provider adapters and account-scoped provider resolution."""
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
    "ChatResult", "LLMProvider", "ProviderMetadata", "StructuredAnalysisError",
    "StructuredAnalysisResult", "AnthropicProvider", "OpenAICompatibleProvider",
    "CloudflareAccessOpenAICompatibleProvider", "get_llm_provider", "build_provider",
]


def build_provider(config) -> LLMProvider:
    """Build the selected adapter; personal credentials never cross account boundaries."""
    from app.services import llm_config
    from app.services.personal_llm import PersonalResolvedConfig

    if config.provider == llm_config.PROVIDER_LOCAL:
        kwargs = dict(
            base_url=config.base_url or "", chat_model=config.chat_model,
            analysis_model=config.analysis_model, copilot_model=config.copilot_model,
            api_key=config.api_key, max_tokens=config.max_tokens,
            timeout_seconds=float(config.timeout_seconds),
        )
        if isinstance(config, PersonalResolvedConfig):
            if not config.api_key.strip():
                raise RuntimeError("Falta la clave personal de LM Studio.")
            # BOTH required: Bearer for LM Studio; CF headers for Cloudflare.
            return CloudflareAccessOpenAICompatibleProvider(
                **kwargs, access_client_id=config.access_client_id,
                access_client_secret=config.access_client_secret,
                access_hostname=config.access_hostname,
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
                raise RuntimeError("La configuración global de Cloudflare Access está incompleta.")
            # Legacy path preserved ONLY until operator enables personal mode.
            kwargs["api_key"] = ""
            return CloudflareAccessOpenAICompatibleProvider(**kwargs, **access)
        return OpenAICompatibleProvider(**kwargs)
    if config.provider == llm_config.PROVIDER_ANTHROPIC:
        from app.services.llm_usage import record_usage_safely
        return AnthropicProvider(
            chat_model=config.chat_model, analysis_model=config.analysis_model,
            copilot_model=config.copilot_model, max_tokens=config.explicit_max_tokens,
            usage_recorder=record_usage_safely,
        )
    raise RuntimeError("Proveedor LLM no admitido.")


def get_llm_provider(db=None) -> LLMProvider:
    """Use personal selection only after the explicit migration feature gate."""
    from app.services import llm_config, personal_llm
    from app.services.personal_resolution import personal_mode_enabled

    info = getattr(db, "info", None) if db is not None else None
    user_id = info.get("authenticated_user_id") if isinstance(info, dict) else None
    if personal_mode_enabled():
        if db is None or user_id is None:
            raise RuntimeError("Inferencia bloqueada: falta la identidad de cuenta verificada.")
        return build_provider(personal_llm.resolve(db, user_id))
    return build_provider(llm_config.resolve(db))

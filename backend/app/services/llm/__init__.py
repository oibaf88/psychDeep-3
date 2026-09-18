"""Provider adapters with separate account choices and shared server credentials."""
from urllib.parse import urlsplit

from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.base import (
    ChatResult, LLMProvider, ProviderMetadata, StructuredAnalysisError,
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
    """Attach credentials only to their operator-pinned destination."""
    from app.services import llm_config
    from app.services.personal_llm import PersonalResolvedConfig
    from app.services.runpod_routing import cloud_credentials_for

    if config.provider == llm_config.PROVIDER_LOCAL:
        kwargs = dict(
            base_url=config.base_url or "", chat_model=config.chat_model,
            analysis_model=config.analysis_model, copilot_model=config.copilot_model,
            api_key=config.api_key, max_tokens=config.max_tokens,
            timeout_seconds=float(config.timeout_seconds),
        )
        # Personal mode must remain bound to its own LM Studio token and
        # Cloudflare Access; never silently promote a user's token to Runpod.
        if isinstance(config, PersonalResolvedConfig):
            if not config.api_key.strip():
                raise RuntimeError("La autenticación de LM Studio no está configurada en Render.")
            return CloudflareAccessOpenAICompatibleProvider(
                **kwargs, access_client_id=config.access_client_id,
                access_client_secret=config.access_client_secret,
                access_hostname=config.access_hostname,
            )
        settings = llm_config.get_settings()
        cloud_key = cloud_credentials_for(config, settings)
        if cloud_key is not None:
            kwargs["api_key"] = cloud_key
            return OpenAICompatibleProvider(**kwargs)

        # Legacy tunnel: require Cloudflare Access credentials, an exact
        # approved HTTPS hostname and the local bearer key before sending any
        # secrets. The Runpod profile above is deliberately evaluated first.
        access = {
            "access_client_id": settings.model_local_cf_access_client_id,
            "access_client_secret": settings.model_local_cf_access_client_secret,
            "access_hostname": settings.model_local_cf_access_host,
        }
        if settings.model_local_cf_access_required or any(value.strip() for value in access.values()):
            if not all(value.strip() for value in access.values()) or not settings.model_local_cf_access_required:
                raise RuntimeError("Cloudflare Access está configurado parcialmente en Render.")
            endpoint = urlsplit(config.base_url or "")
            if (endpoint.scheme != "https" or endpoint.hostname != settings.model_local_cf_access_host.strip().lower()
                    or endpoint.port not in (None, 443) or endpoint.username or endpoint.password):
                raise RuntimeError("LOCAL_ENDPOINT_HOST_NOT_APPROVED")
            if not settings.model_local_api_key.strip():
                raise RuntimeError("Falta MODEL_LOCAL_API_KEY en Render.")
            kwargs["api_key"] = settings.model_local_api_key
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
    """Use account-scoped resolution only after an explicitly staged cutover."""
    from app.services import llm_config, local_llm_access, personal_llm
    from app.services.personal_resolution import personal_mode_enabled

    user = local_llm_access.request_user(db)
    if personal_mode_enabled():
        if db is None or user is None:
            raise RuntimeError("Inferencia bloqueada: falta la identidad de cuenta verificada.")
        config = personal_llm.resolve(db, user.id)
        if config.provider == llm_config.PROVIDER_LOCAL:
            local_llm_access.assert_can_use_local_llm(user)
        return build_provider(config)
    config = llm_config.resolve(db)
    if config.provider == llm_config.PROVIDER_LOCAL:
        local_llm_access.assert_can_use_local_llm(user)
    return build_provider(config)

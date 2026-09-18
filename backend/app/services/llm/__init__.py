"""Provider adapters with separate account choices and shared server credentials."""
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
    """Combine an account's model choice with operator-owned credentials."""
    from urllib.parse import urlparse

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
                raise RuntimeError("La autenticación de LM Studio no está configurada en Render.")
            return CloudflareAccessOpenAICompatibleProvider(
                **kwargs, access_client_id=config.access_client_id,
                access_client_secret=config.access_client_secret,
                access_hostname=config.access_hostname,
            )
        settings = llm_config.get_settings()
        # cloud-tuned reuses the OpenAI-compatible transport, NOT the local
        # Cloudflare Access transport. Never attach the local Access service
        # credentials or the local LM Studio bearer to a cloud provider.
        # A runtime override has source='runtime' and cannot impersonate this
        # explicitly selected environment deployment.
        if config.source == "environment" and settings.model_deployment_alias.strip() == "cloud-tuned":
            endpoint = urlparse(config.base_url or "")
            if not settings.model_cloud_api_key.strip():
                raise RuntimeError("MODEL_CLOUD_API_KEY is required for cloud-tuned inference.")
            if not endpoint.hostname or (settings.is_production and endpoint.scheme != "https"):
                raise RuntimeError("cloud-tuned requires a configured HTTPS endpoint in production.")
            if llm_config._hostname_is_private(endpoint.hostname) and settings.is_production:
                raise RuntimeError("cloud-tuned cannot target a private or loopback endpoint in production.")
            return OpenAICompatibleProvider(**kwargs)
        # Transitional path: never silently remove the LM Studio bearer token
        # when Cloudflare Access is enabled. Full personal routing is gated by
        # LLM_PERSONAL_MODE until the operator completes deployment checks.
        access = {
            "access_client_id": settings.model_local_cf_access_client_id,
            "access_client_secret": settings.model_local_cf_access_client_secret,
            "access_hostname": settings.model_local_cf_access_host,
        }
        if settings.model_local_cf_access_required or any(value.strip() for value in access.values()):
            if not all(value.strip() for value in access.values()) or not settings.model_local_cf_access_required:
                raise RuntimeError("Cloudflare Access está configurado parcialmente en Render.")
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
    from app.services import llm_config, personal_llm
    from app.services.personal_resolution import personal_mode_enabled

    info = getattr(db, "info", None) if db is not None else None
    user_id = info.get("authenticated_user_id") if isinstance(info, dict) else None
    if personal_mode_enabled():
        if db is None or user_id is None:
            raise RuntimeError("Inferencia bloqueada: falta la identidad de cuenta verificada.")
        return build_provider(personal_llm.resolve(db, user_id))
    return build_provider(llm_config.resolve(db))

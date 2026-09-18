"""Cloud inference must never inherit Cloudflare/LM Studio credentials."""
import pytest

from app.config import get_settings
from app.services import llm_config
from app.services.llm import build_provider
from app.services.llm.openai_compatible import OpenAICompatibleProvider
from app.services.llm.cloudflare_access import CloudflareAccessOpenAICompatibleProvider


@pytest.fixture(autouse=True)
def clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def cloud_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MODEL_DEPLOYMENT_ALIAS", "cloud-tuned")
    monkeypatch.setenv("MODEL_CLOUD_BASE_URL", "https://api.runpod.ai/v2/example-id/openai/v1")
    monkeypatch.setenv("MODEL_CLOUD_API_KEY", "synthetic-cloud-secret")
    monkeypatch.setenv("MODEL_CLOUD_CHAT_MODEL", "TsinghuaC3I/Llama-3.1-8B-UltraMedical")
    monkeypatch.setenv("MODEL_CLOUD_ANALYSIS_MODEL", "TsinghuaC3I/Llama-3.1-8B-UltraMedical")
    monkeypatch.setenv("MODEL_LOCAL_CF_ACCESS_REQUIRED", "true")
    monkeypatch.setenv("MODEL_LOCAL_CF_ACCESS_HOST", "ai.example.org")
    monkeypatch.setenv("MODEL_LOCAL_CF_ACCESS_CLIENT_ID", "synthetic-access-id")
    monkeypatch.setenv("MODEL_LOCAL_CF_ACCESS_CLIENT_SECRET", "synthetic-access-secret")
    monkeypatch.setenv("MODEL_LOCAL_API_KEY", "synthetic-local-secret")
    get_settings.cache_clear()


def test_cloud_default_uses_only_cloud_api_key_even_when_local_access_enabled(monkeypatch):
    cloud_env(monkeypatch)
    provider = build_provider(llm_config.environment_config())
    assert type(provider) is OpenAICompatibleProvider
    assert not isinstance(provider, CloudflareAccessOpenAICompatibleProvider)
    assert provider._api_key == "synthetic-cloud-secret"
    assert provider.base_url == "https://api.runpod.ai/v2/example-id/openai/v1"


def test_cloud_default_fails_closed_without_own_key(monkeypatch):
    cloud_env(monkeypatch)
    monkeypatch.setenv("MODEL_CLOUD_API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="MODEL_CLOUD_API_KEY"):
        build_provider(llm_config.environment_config())


@pytest.mark.parametrize("base_url", ["http://api.runpod.ai/v2/example-id/openai/v1", "https://127.0.0.1:8000/v1", ""])
def test_cloud_default_rejects_non_https_private_or_missing_endpoints(monkeypatch, base_url):
    cloud_env(monkeypatch)
    monkeypatch.setenv("MODEL_CLOUD_BASE_URL", base_url)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="endpoint"):
        build_provider(llm_config.environment_config())


def test_runtime_local_override_is_not_mistaken_for_cloud(monkeypatch):
    cloud_env(monkeypatch)
    # Existing runtime selections retain their own local-Access contract.
    config = llm_config.ResolvedConfig(
        provider=llm_config.PROVIDER_LOCAL,
        chat_model="local-model",
        analysis_model="local-model",
        base_url="https://ai.example.org/v1",
        api_key="synthetic-local-secret",
        source="runtime",
    )
    provider = build_provider(config)
    assert isinstance(provider, CloudflareAccessOpenAICompatibleProvider)
    assert provider._api_key == "synthetic-local-secret"

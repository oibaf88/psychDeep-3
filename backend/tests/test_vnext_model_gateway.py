import pytest

from app.config import get_settings
from app.services.model_gateway import ModelGateway, ModelUnavailable


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_unknown_deployment_alias_is_rejected(monkeypatch):
    monkeypatch.setenv("MODEL_DEPLOYMENT_ALIAS", "user-supplied-provider")
    with pytest.raises(ModelUnavailable, match="MODEL_DEPLOYMENT_NOT_APPROVED"):
        ModelGateway()


def test_commercial_bridge_is_disabled_by_default(monkeypatch):
    monkeypatch.setenv("MODEL_DEPLOYMENT_ALIAS", "commercial-approved")
    monkeypatch.setenv("MODEL_ALLOW_COMMERCIAL", "false")
    with pytest.raises(ModelUnavailable, match="COMMERCIAL_MODEL_NOT_APPROVED"):
        ModelGateway()


def test_production_local_tunnel_requires_https(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MODEL_DEPLOYMENT_ALIAS", "local-tunnel")
    monkeypatch.setenv("MODEL_LOCAL_BASE_URL", "http://example.org/v1")
    monkeypatch.setenv("MODEL_LOCAL_CHAT_MODEL", "test-model")
    monkeypatch.setenv("MODEL_LOCAL_ANALYSIS_MODEL", "test-model")
    gateway = ModelGateway()
    with pytest.raises(ModelUnavailable, match="MODEL_ENDPOINT_REQUIRES_HTTPS"):
        gateway.provider()


def test_production_rejects_private_model_endpoint(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MODEL_DEPLOYMENT_ALIAS", "local-tunnel")
    monkeypatch.setenv("MODEL_LOCAL_BASE_URL", "https://127.0.0.1:1234/v1")
    monkeypatch.setenv("MODEL_LOCAL_CHAT_MODEL", "test-model")
    monkeypatch.setenv("MODEL_LOCAL_ANALYSIS_MODEL", "test-model")
    gateway = ModelGateway()
    with pytest.raises(ModelUnavailable, match="MODEL_ENDPOINT_PRIVATE_FROM_CLOUD"):
        gateway.provider()


def test_local_tunnel_does_not_need_commercial_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MODEL_DEPLOYMENT_ALIAS", "local-tunnel")
    monkeypatch.setenv("MODEL_LOCAL_BASE_URL", "https://llm.example.org/v1")
    monkeypatch.setenv("MODEL_LOCAL_CHAT_MODEL", "test-model")
    monkeypatch.setenv("MODEL_LOCAL_ANALYSIS_MODEL", "test-model")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = ModelGateway().provider()
    assert provider is not None

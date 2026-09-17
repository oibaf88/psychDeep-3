"""Regression tests for source-specific LLM API key routing (no network)."""
from types import SimpleNamespace

import pytest

from app.services import llm_config
from app.services.llm import build_provider

RUNPOD = "https://api.runpod.ai/v2/test-endpoint/openai/v1"
MODEL = "empirischtech/Llama-3.1-8B-Instruct-MedQA"
LOCAL = "https://ai.bfab.io/v1"


def fake_settings(**extra):
    values = dict(
        model_cloud_base_url=RUNPOD,
        model_cloud_api_key="cloud-only-secret",
        model_cloud_chat_model=MODEL,
        model_cloud_analysis_model=MODEL,
        model_cloud_copilot_model=MODEL,
        model_local_cf_access_required=True,
        model_local_cf_access_client_id="access-id",
        model_local_cf_access_client_secret="access-secret",
        model_local_cf_access_host="ai.bfab.io",
        model_local_api_key="local-only-secret",
    )
    values.update(extra)
    return SimpleNamespace(**values)


def config(base_url=RUNPOD, model=MODEL):
    return llm_config.ResolvedConfig(
        provider=llm_config.PROVIDER_LOCAL,
        chat_model=model,
        analysis_model=model,
        copilot_model=model,
        base_url=base_url,
        api_key="legacy-local-secret",
        max_tokens=1024,
        timeout_seconds=30,
        source="runtime",
    )


def test_runpod_only_receives_cloud_key(monkeypatch):
    monkeypatch.setattr(llm_config, "get_settings", fake_settings)
    monkeypatch.setattr("app.services.llm.OpenAICompatibleProvider", lambda **kw: kw)
    monkeypatch.setattr("app.services.llm.CloudflareAccessOpenAICompatibleProvider", lambda **kw: pytest.fail("Cloudflare used for Runpod"))
    got = build_provider(config())
    assert got["api_key"] == "cloud-only-secret"
    assert got["base_url"] == RUNPOD


def test_cloud_key_not_sent_to_cloudflare(monkeypatch):
    monkeypatch.setattr(llm_config, "get_settings", fake_settings)
    monkeypatch.setattr("app.services.llm.CloudflareAccessOpenAICompatibleProvider", lambda **kw: kw)
    got = build_provider(config(base_url=LOCAL))
    assert got["api_key"] == "local-only-secret"
    assert got["access_client_secret"] == "access-secret"


def test_runpod_different_endpoint_cannot_receive_local_key(monkeypatch):
    monkeypatch.setattr(llm_config, "get_settings", fake_settings)
    with pytest.raises(RuntimeError, match="LOCAL_ENDPOINT_HOST_NOT_APPROVED"):
        build_provider(config(base_url="https://api.runpod.ai/v2/unapproved/openai/v1"))


def test_cloud_without_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(llm_config, "get_settings", lambda: fake_settings(model_cloud_api_key=""))
    with pytest.raises(RuntimeError, match="RUNPOD_CREDENTIAL_NOT_CONFIGURED"):
        build_provider(config())

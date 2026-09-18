"""Runpod routing invariants; no network, GPU or secrets required."""
from types import SimpleNamespace

import pytest

from app.services.runpod_routing import cloud_credentials_for, validated_runpod_url

BASE = "https://api.runpod.ai/v2/test-endpoint/openai/v1"
# A deliberately fictional test-only ID, NOT a Hugging Face model to deploy.
MODEL = "test-fixture/biomedical-llama-3.1-reviewed-model"


def settings(**overrides):
    config = dict(
        model_cloud_base_url=BASE,
        model_cloud_api_key="runpod-secret",
        model_cloud_chat_model=MODEL,
        model_cloud_analysis_model=MODEL,
        model_cloud_copilot_model=MODEL,
    )
    config.update(overrides)
    return SimpleNamespace(**config)


def deployment(**overrides):
    config = dict(base_url=BASE, chat_model=MODEL, analysis_model=MODEL, copilot_model=MODEL)
    config.update(overrides)
    return SimpleNamespace(**config)


def test_validates_runpod_openai_compatible_base_url():
    assert validated_runpod_url(BASE) == BASE
    assert validated_runpod_url(BASE + "/") == BASE


@pytest.mark.parametrize("url", [
    "http://api.runpod.ai/v2/test-endpoint/openai/v1",
    "https://api.runpod.ai.evil.example/v2/test-endpoint/openai/v1",
    "https://api.runpod.ai/v2/test-endpoint/run",
    "https://api.runpod.ai/v2/test-endpoint/openai/v1?token=leak",
    "https://attacker@api.runpod.ai/v2/test-endpoint/openai/v1",
    "https://api.runpod.ai/v2/../openai/v1",
    "https://api.runpod.ai/v2/test-endpoint/openai/v1/chat/completions",
])
def test_rejects_unapproved_url(url):
    with pytest.raises(RuntimeError, match="RUNPOD_ENDPOINT_INVALID"):
        validated_runpod_url(url)


def test_cloud_key_only_for_exact_pinned_endpoint_and_model():
    assert cloud_credentials_for(deployment(), settings()) == "runpod-secret"
    assert cloud_credentials_for(deployment(base_url="https://ai.bfab.io/v1"), settings()) is None
    with pytest.raises(RuntimeError, match="RUNPOD_ENDPOINT_NOT_APPROVED"):
        cloud_credentials_for(deployment(base_url=BASE + "/chat/completions"), settings())


def test_missing_key_fails_closed():
    with pytest.raises(RuntimeError, match="RUNPOD_CREDENTIAL_NOT_CONFIGURED"):
        cloud_credentials_for(deployment(), settings(model_cloud_api_key=""))


def test_missing_model_selection_fails_closed():
    with pytest.raises(RuntimeError, match="RUNPOD_MODEL_NOT_APPROVED"):
        cloud_credentials_for(deployment(), settings(
            model_cloud_chat_model="", model_cloud_analysis_model="", model_cloud_copilot_model=""
        ))


def test_unknown_model_fails_closed():
    with pytest.raises(RuntimeError, match="RUNPOD_MODEL_NOT_APPROVED"):
        cloud_credentials_for(deployment(analysis_model="unknown-model"), settings())


def test_invalid_pinned_cloud_url_does_not_get_credential():
    bad = "https://evil.example/v2/test-endpoint/openai/v1"
    with pytest.raises(RuntimeError, match="RUNPOD_ENDPOINT_INVALID"):
        cloud_credentials_for(deployment(base_url=bad), settings(model_cloud_base_url=bad))

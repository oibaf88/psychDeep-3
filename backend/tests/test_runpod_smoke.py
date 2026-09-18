"""Offline verification of the read-only Runpod smoke script URL parser."""
import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke_runpod.py"
SPEC = importlib.util.spec_from_file_location("smoke_runpod", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_valid_base():
    base = "https://api.runpod.ai/v2/abc_123/openai/v1"
    assert MODULE.validate_base_url(base) == base
    assert MODULE.validate_base_url(base + "/") == base


@pytest.mark.parametrize("url", [
    "http://api.runpod.ai/v2/abc/openai/v1",
    "https://example.com/v2/abc/openai/v1",
    "https://api.runpod.ai/v2/abc/run",
    "https://api.runpod.ai/v2/abc/openai/v1/chat/completions",
    "https://api.runpod.ai/v2/abc/openai/v1?key=secret",
])
def test_invalid_base(url):
    with pytest.raises(ValueError):
        MODULE.validate_base_url(url)


def test_missing_credentials_fails_without_network(monkeypatch):
    monkeypatch.setenv("MODEL_CLOUD_BASE_URL", "https://api.runpod.ai/v2/abc/openai/v1")
    monkeypatch.delenv("MODEL_CLOUD_API_KEY", raising=False)
    monkeypatch.setenv("MODEL_CLOUD_CHAT_MODEL", "synthetic-model")
    monkeypatch.setattr(MODULE, "request_json", lambda *args, **kwargs: pytest.fail("network called"))
    assert MODULE.main() == 1

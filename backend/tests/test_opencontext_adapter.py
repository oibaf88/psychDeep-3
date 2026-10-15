from __future__ import annotations

import json
from unittest.mock import patch
from urllib.error import URLError

import pytest

from app.services.opencontext_adapter import OpenContextClient, OpenContextConfig


def _config(**overrides):
    values = dict(
        enabled=True,
        base_url="https://context.example.test",
        token="synthetic-test-token-not-for-use",
        agent_id="psychdeep-agent1",
        timeout_seconds=2,
        max_context_tokens=500,
    )
    values.update(overrides)
    return OpenContextConfig(**values)


def test_disabled_by_default_env(monkeypatch):
    monkeypatch.delenv("OPENCONTEXT_ENABLED", raising=False)
    monkeypatch.delenv("OPENCONTEXT_BASE_URL", raising=False)
    monkeypatch.delenv("OPENCONTEXT_API_TOKEN", raising=False)
    client = OpenContextClient(OpenContextConfig.from_env())
    assert client.enabled is False
    assert client.search("synthetic query") == {"ok": False, "disabled": True}


def test_enabled_requires_token_and_url():
    with pytest.raises(ValueError):
        OpenContextClient(_config(token=""))
    with pytest.raises(ValueError):
        OpenContextClient(_config(base_url=""))


def test_rejects_plain_http_unless_explicit_local_development():
    with pytest.raises(ValueError):
        OpenContextClient(_config(base_url="http://context.example.test"))
    client = OpenContextClient(
        _config(base_url="http://127.0.0.1:8765"),
        allow_local_http=True,
    )
    assert client.enabled is True


def test_rejects_url_with_embedded_credentials():
    with pytest.raises(ValueError):
        OpenContextClient(_config(base_url="https://user:pass@context.example.test"))


def test_search_is_bounded_and_checks_application_result():
    client = OpenContextClient(_config())
    with patch.object(client, "_request", return_value={"ok": True, "hits": []}) as request:
        client.search(" craving ", k=100, budget_tokens=99999)
    request.assert_called_once_with("POST", "/api/search", {
        "query": "craving",
        "k": 8,
        "budget_tokens": 500,
    })


def test_interaction_requires_unique_message_ids():
    client = OpenContextClient(_config())
    with pytest.raises(ValueError):
        client.ingest_interaction(
            session_id="synth-session",
            event_id="synth-event",
            messages=[
                {"message_id": "m1", "role": "user", "content": "synthetic"},
                {"message_id": "m1", "role": "assistant", "content": "synthetic"},
            ],
        )


def test_interaction_keeps_full_envelope_for_api():
    client = OpenContextClient(_config())
    messages = [{
        "message_id": "m1",
        "role": "user",
        "speaker_id": "person:synthetic",
        "timestamp": "2026-10-15T10:00:00+02:00",
        "content": "Synthetic test only",
        "extra_metadata": {"source": "test"},
    }]
    with patch.object(client, "_request", return_value={"ok": True}) as request:
        client.ingest_interaction(
            session_id="synthetic-session",
            event_id="synthetic-event",
            messages=messages,
            metadata={"timezone": "Europe/Madrid"},
        )
    envelope = request.call_args.args[2]
    assert envelope["messages"] == messages
    assert envelope["metadata"]["timezone"] == "Europe/Madrid"
    assert envelope["agent_id"] == "psychdeep-agent1"


def test_application_error_is_not_treated_as_success(monkeypatch):
    client = OpenContextClient(_config())
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, _limit): return json.dumps({"ok": False, "error": "synthetic"}).encode()
    monkeypatch.setattr(client._opener, "open", lambda *a, **k: FakeResponse())
    with pytest.raises(RuntimeError, match="unsuccessful application result"):
        client.health()


def test_transport_exception_does_not_leak_request_details(monkeypatch):
    client = OpenContextClient(_config())
    monkeypatch.setattr(client._opener, "open", lambda *a, **k: (_ for _ in ()).throw(URLError("synthetic error")))
    with pytest.raises(RuntimeError, match="transport failure"):
        client.health()

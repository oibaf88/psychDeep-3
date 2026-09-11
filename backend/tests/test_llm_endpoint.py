"""Provider boundaries for Claude default and local Gemma 2 fallback."""
from __future__ import annotations

import copy
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from app.services import llm_config
from app.services.llm import AnthropicProvider, build_provider
from app.services.llm.base import StructuredAnalysisError
from app.services.llm.openai_compatible import OpenAICompatibleProvider, extract_json_object


SCHEMA = {
    "name": "record",
    "input_schema": {"type": "object", "properties": {"a": {"type": "number"}}, "required": ["a"]},
}


def _response(status_code=200, payload=None, text="OK"):
    body = payload if payload is not None else {
        "id": "chatcmpl-test",
        "model": "gemma-2-2b-it",
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 3},
    }
    return SimpleNamespace(status_code=status_code, json=lambda: body)


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, url, headers=None, json=None):
        self.requests.append({"url": url, "headers": dict(headers or {}), "json": copy.deepcopy(json or {})})
        return self.responses.pop(0)


def _settings(*, provider="anthropic", allow_override=False, production=False, anthropic_key="anthropic-test"):
    return SimpleNamespace(
        llm_default_provider=provider,
        llm_allow_runtime_override=allow_override,
        llm_openai_compatible_base_url="http://host.docker.internal:1234/v1",
        llm_openai_compatible_api_key="lm-test-token",
        llm_openai_compatible_chat_model="gemma-2-2b-it",
        llm_openai_compatible_analysis_model="gemma-2-2b-it",
        llm_openai_compatible_copilot_model="",
        llm_openai_compatible_max_tokens=8192,
        llm_openai_compatible_timeout_seconds=300,
        local_copilot_model="gemma-2-2b-it",
        anthropic_api_key=anthropic_key,
        anthropic_chat_model="claude-opus-5",
        anthropic_analysis_model="claude-opus-5",
        anthropic_copilot_model="",
        anthropic_max_tokens=8192,
        anthropic_max_tokens_chat=0,
        anthropic_max_tokens_analysis=0,
        anthropic_chat_effort="medium",
        anthropic_analysis_effort="high",
        anthropic_copilot_effort="",
        copilot_model="claude-opus-5",
        copilot_effort="medium",
        max_tokens_chat=8192,
        max_tokens_analysis=8192,
        is_production=production,
    )


class JsonRecoveryTests(unittest.TestCase):
    def test_recovers_plain_fenced_and_nested_objects(self):
        self.assertEqual(extract_json_object('{"a": 1}'), {"a": 1})
        self.assertEqual(extract_json_object('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(
            extract_json_object('Antes {"outer": {"inner": true}, "quote": "{texto}"} después'),
            {"outer": {"inner": True}, "quote": "{texto}"},
        )

    def test_refuses_non_objects_and_prose(self):
        for text in ("[1, 2]", "respuesta sin JSON"):
            with self.assertRaises(ValueError):
                extract_json_object(text)


class GemmaProviderTests(unittest.TestCase):
    def _provider(self, **kwargs):
        return OpenAICompatibleProvider(
            base_url=kwargs.pop("base_url", "http://localhost:1234/v1"),
            chat_model=kwargs.pop("chat_model", "gemma-2-2b-it"),
            analysis_model=kwargs.pop("analysis_model", "gemma-2-2b-it"),
            **kwargs,
        )

    def test_chat_uses_openai_path_gemma_id_and_optional_bearer_token(self):
        client = _FakeClient([_response(text="hola")])
        with patch("httpx.Client", return_value=client):
            result = self._provider(api_key="token").chat("sistema", [{"role": "user", "content": "hola"}])
        self.assertEqual(result.text, "hola")
        self.assertEqual(result.metadata.provider, "openai_compatible")
        self.assertEqual(client.requests[0]["url"], "http://localhost:1234/v1/chat/completions")
        self.assertEqual(client.requests[0]["headers"]["Authorization"], "Bearer token")
        self.assertEqual(client.requests[0]["json"]["model"], "gemma-2-2b-it")

    def test_structured_analysis_recovers_fenced_json_and_fails_closed(self):
        client = _FakeClient([_response(text='```json\n{"a": 3}\n```')])
        with patch("httpx.Client", return_value=client):
            result = self._provider().analyze_structured("sistema", "texto", SCHEMA)
        self.assertEqual(result.value, {"a": 3})
        self.assertEqual(client.requests[0]["json"]["temperature"], 0)
        self.assertIn("JSON Schema", client.requests[0]["json"]["messages"][0]["content"])

        bad = _FakeClient([_response(text="sin JSON")])
        with patch("httpx.Client", return_value=bad):
            with self.assertRaises(StructuredAnalysisError) as malformed:
                self._provider().analyze_structured("s", "t", SCHEMA)
        self.assertEqual(malformed.exception.safe_kind, "invalid_output")

    def test_docker_rewrites_loopback_to_host_gateway(self):
        from app.services.llm.openai_compatible import get_candidate_base_urls

        with patch("os.environ.get", side_effect=lambda key, default="": "true" if key == "RUNNING_IN_DOCKER" else default):
            candidates = get_candidate_base_urls("http://localhost:1234/v1")
        self.assertEqual(candidates[0], "http://host.docker.internal:1234/v1")


class ProviderSelectionTests(unittest.TestCase):
    def tearDown(self):
        llm_config.invalidate_cache()

    def test_claude_is_the_product_default_and_key_never_serialises(self):
        with patch.object(llm_config, "get_settings", return_value=_settings()):
            config = llm_config.environment_config()
            public = config.public_dict()
        self.assertEqual(config.provider, llm_config.PROVIDER_ANTHROPIC)
        self.assertEqual(config.chat_model, "claude-opus-5")
        self.assertTrue(public["uses_server_api_key"])
        self.assertNotIn("api_key", public)
        self.assertNotIn("anthropic-test", str(public))

    def test_claude_factory_uses_server_key_not_runtime_payload(self):
        config = llm_config.ResolvedConfig(
            provider=llm_config.PROVIDER_ANTHROPIC,
            chat_model="claude-opus-5",
            analysis_model="claude-opus-5",
            api_key="browser-must-not-win",
        )
        with patch("app.services.llm.anthropic_provider.get_settings", return_value=_settings()):
            provider = build_provider(config)
        self.assertIsInstance(provider, AnthropicProvider)
        self.assertEqual(provider._api_key, "anthropic-test")

    def test_local_gemma_is_selectable_and_uses_its_endpoint(self):
        with patch.object(llm_config, "get_settings", return_value=_settings(provider="openai_compatible")):
            config = llm_config.environment_config()
        provider = build_provider(config)
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(config.chat_model, "gemma-2-2b-it")

    def test_validation_accepts_only_the_two_intended_providers(self):
        with patch.object(llm_config, "backend_runtime", return_value="local"):
            claude = llm_config.validate(
                provider="anthropic", base_url="http://ignored.example/v1", chat_model="claude-opus-5",
                analysis_model="claude-opus-5", max_tokens=8192, timeout_seconds=300,
            )
            self.assertIsNone(claude["base_url"])
            gemma = llm_config.validate(
                provider="openai_compatible", base_url="http://localhost:1234", chat_model="gemma-2-2b-it",
                analysis_model="gemma-2-2b-it", max_tokens=8192, timeout_seconds=300,
            )
            self.assertEqual(gemma["base_url"], "http://localhost:1234/v1")
            with self.assertRaises(llm_config.LLMConfigError):
                llm_config.validate(
                    provider="unknown", base_url="http://localhost:1234", chat_model="m", analysis_model="m",
                    max_tokens=8192, timeout_seconds=300,
                )

    def test_cloud_backend_rejects_lan_or_plain_http_for_gemma(self):
        with patch.dict(os.environ, {"RENDER": "true"}, clear=False), patch.object(
            llm_config, "get_settings", return_value=_settings(production=True)
        ):
            lan = llm_config.endpoint_reachability("http://192.168.1.10:1234/v1")
            insecure = llm_config.endpoint_reachability("http://model.example.test/v1")
        self.assertFalse(lan["ok"])
        self.assertIn("Cloudflare", lan["reason"])
        self.assertFalse(insecure["ok"])
        self.assertIn("HTTPS", insecure["reason"])


class DeploymentGuardTests(unittest.TestCase):
    def test_claude_default_and_runtime_override_off_are_tracked(self):
        from app.config import Settings
        import os

        self.assertEqual(Settings.model_fields["llm_default_provider"].default, "anthropic")
        self.assertFalse(Settings.model_fields["llm_allow_runtime_override"].default)

        # Resolve the path relative to the tests directory to support running from anywhere
        render_yaml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "render.yaml")
        with open(render_yaml_path, encoding="utf-8") as blueprint:
            text = blueprint.read()
        self.assertIn("- key: ANTHROPIC_API_KEY\n        sync: false", text)
        provider_index = text.index("LLM_DEFAULT_PROVIDER")
        self.assertIn("value: anthropic", text[provider_index : provider_index + 100])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

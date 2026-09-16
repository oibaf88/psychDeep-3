"""Test both backend-owned authentication layers with disposable fixture values."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import llm_config
from app.services.llm import build_provider
from app.services.llm.cloudflare_access import CloudflareAccessOpenAICompatibleProvider
from app.services.llm.openai_compatible import OpenAICompatibleProvider


class FakeClient:
    requests = []

    def __init__(self, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def post(self, url, headers=None, json=None):
        FakeClient.requests.append((url, dict(headers or {}), json))
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "OK"}}]},
        )


def config(url="https://ai.bfab.io/v1"):
    return llm_config.ResolvedConfig(
        provider=llm_config.PROVIDER_LOCAL,
        base_url=url,
        chat_model="test-model",
        analysis_model="test-model",
        api_key="obsolete-legacy-token-do-not-forward",
    )


def settings(required=True, host="ai.bfab.io", client_id="test-id", secret="test-secret", lm_key="shared-lm-token"):
    return SimpleNamespace(
        model_local_cf_access_required=required,
        model_local_cf_access_host=host,
        model_local_cf_access_client_id=client_id,
        model_local_cf_access_client_secret=secret,
        model_local_api_key=lm_key,
    )


class AccessGatewayTests(unittest.TestCase):
    def setUp(self):
        FakeClient.requests = []

    def test_sends_access_credentials_and_shared_lm_studio_bearer_token(self):
        with patch.object(llm_config, "get_settings", return_value=settings()):
            provider = build_provider(config())
        self.assertIsInstance(provider, CloudflareAccessOpenAICompatibleProvider)
        with patch("httpx.Client", FakeClient):
            provider.chat("system", [{"role": "user", "content": "test"}])
        url, headers, _ = FakeClient.requests[0]
        self.assertEqual(url, "https://ai.bfab.io/v1/chat/completions")
        self.assertEqual(headers["CF-Access-Client-Id"], "test-id")
        self.assertEqual(headers["CF-Access-Client-Secret"], "test-secret")
        self.assertEqual(headers["Authorization"], "Bearer shared-lm-token")
        self.assertNotIn("obsolete-legacy-token-do-not-forward", str(headers))

    def test_fails_closed_when_required_service_token_or_bearer_is_missing(self):
        for credentials in (
            settings(client_id="", secret=""),
            settings(client_id="", secret="test-secret"),
            settings(client_id="test-id", secret=""),
            settings(host=""),
            settings(lm_key=""),
        ):
            with self.subTest(credentials=bool(credentials.model_local_cf_access_client_id), lm=bool(credentials.model_local_api_key)):
                with patch.object(llm_config, "get_settings", return_value=credentials):
                    with self.assertRaises(RuntimeError):
                        build_provider(config())

    def test_rejects_other_host_and_http_without_sending_secrets(self):
        for url in (
            "https://not-ai.bfab.io/v1",
            "http://ai.bfab.io/v1",
            "https://ai.bfab.io:8443/v1",
            "https://user@ai.bfab.io/v1",
        ):
            with self.subTest(url=url):
                with patch.object(llm_config, "get_settings", return_value=settings()):
                    with self.assertRaises(RuntimeError):
                        build_provider(config(url))
        self.assertEqual(FakeClient.requests, [])

    def test_access_not_silently_bypassed_when_partially_configured(self):
        with patch.object(
            llm_config, "get_settings", return_value=settings(required=False, secret=""),
        ):
            with self.assertRaises(RuntimeError):
                build_provider(config())

    def test_other_compatible_endpoints_retain_opt_in_legacy_mode_before_cutover(self):
        with patch.object(
            llm_config, "get_settings",
            return_value=settings(required=False, host="", client_id="", secret=""),
        ):
            provider = build_provider(config("http://localhost:1234/v1"))
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertNotIsInstance(provider, CloudflareAccessOpenAICompatibleProvider)


if __name__ == "__main__":
    unittest.main()

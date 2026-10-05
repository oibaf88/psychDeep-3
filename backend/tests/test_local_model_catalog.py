"""The local model id comes from LM Studio's catalog, not from a library default."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.llm.base import StructuredAnalysisError
from app.services.llm.openai_compatible import OpenAICompatibleProvider
from app.services.local_model_catalog import Catalog, LocalModel, fetch_catalog, select_model


def _settings_call(**kwargs):
    return fetch_catalog(
        endpoint="https://ai.bfab.io/v1",
        api_key="lm-test",
        access_client_id="id",
        access_client_secret="secret",
        access_hostname="ai.bfab.io",
        **kwargs,
    )


class SelectModelTests(unittest.TestCase):
    def test_unreachable_catalog_keeps_the_requested_id(self):
        catalog = Catalog((), False)
        self.assertEqual(select_model("configured-model", catalog), "configured-model")

    def test_unconfirmed_library_default_is_not_sent_when_the_catalog_is_down(self):
        catalog = Catalog((), False)
        self.assertEqual(select_model("gemma-2-2b-it", catalog), "")

    def test_unknown_requested_id_uses_the_only_loaded_model(self):
        catalog = Catalog((LocalModel("retired-default", False), LocalModel("loaded-model", True)), True)
        self.assertEqual(select_model("gemma-2-2b-it", catalog), "loaded-model")

    def test_known_requested_id_wins_over_another_loaded_model(self):
        catalog = Catalog((LocalModel("chosen", False), LocalModel("loaded-model", True)), True)
        self.assertEqual(select_model("chosen", catalog), "chosen")

    def test_several_unloaded_models_do_not_guess(self):
        catalog = Catalog((LocalModel("one", False), LocalModel("two", False)), True)
        self.assertEqual(select_model("missing", catalog), "")

    def test_single_advertised_model_is_used_when_nothing_was_chosen(self):
        catalog = Catalog((LocalModel("only-model", False),), True)
        self.assertEqual(select_model("", catalog), "only-model")


class FetchCatalogTests(unittest.TestCase):
    def tearDown(self):
        from app.services.local_model_catalog import clear_catalog_cache
        clear_catalog_cache()

    def test_reads_loaded_state_and_sends_the_application_user_agent(self):
        calls = []

        class Response:
            def __init__(self, payload):
                self.status_code = 200
                self.headers = {"content-type": "application/json"}
                self._payload = payload

            def json(self):
                return self._payload

        class Client:
            def __init__(self, **_kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def get(self, url, headers=None):
                calls.append((url, dict(headers or {})))
                if url.endswith("/api/v0/models"):
                    return Response({"data": [
                        {"id": "loaded-model", "state": "loaded"},
                        {"id": "other-model", "state": "not-loaded"},
                    ]})
                return Response({"data": [{"id": "loaded-model"}, {"id": "v1-only"}]})

        with patch("httpx.Client", Client):
            catalog = _settings_call()
        self.assertTrue(catalog.reachable)
        by_id = {model.id: model.loaded for model in catalog.models}
        self.assertEqual(by_id["loaded-model"], True)
        self.assertEqual(by_id["other-model"], False)
        self.assertIn("v1-only", by_id)
        self.assertTrue(all(headers["User-Agent"] == "PsychDeep-API/1" for _, headers in calls))
        self.assertTrue(all("python-httpx" not in headers["User-Agent"] for _, headers in calls))
        self.assertTrue(all(url.startswith("https://ai.bfab.io/") for url, _ in calls))

    def test_html_challenge_is_not_a_model_list(self):
        class Response:
            status_code = 403
            headers = {"content-type": "text/html; charset=UTF-8"}

            def json(self):
                raise AssertionError("challenge HTML must not be parsed as a catalog")

        class Client:
            def __init__(self, **_kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def get(self, url, headers=None):
                return Response()

        with patch("httpx.Client", Client):
            catalog = _settings_call()
        self.assertFalse(catalog.reachable)
        self.assertEqual(catalog.models, ())

    def test_refuses_a_host_that_is_not_the_approved_tunnel(self):
        with patch("httpx.Client") as client:
            catalog = fetch_catalog(
                endpoint="https://evil.example/v1",
                api_key="lm-test",
                access_client_id="id",
                access_client_secret="secret",
                access_hostname="ai.bfab.io",
            )
        self.assertFalse(catalog.reachable)
        client.assert_not_called()


class ChallengeClassificationTests(unittest.TestCase):
    def test_html_403_is_reported_as_a_cloudflare_challenge(self):
        captured = {}

        class Client:
            def __init__(self, **_kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def post(self, url, headers=None, json=None):
                captured["headers"] = dict(headers or {})
                return SimpleNamespace(
                    status_code=403,
                    headers={"content-type": "text/html; charset=UTF-8"},
                    json=lambda: {},
                )

        provider = OpenAICompatibleProvider(
            base_url="https://ai.bfab.io/v1", chat_model="m", analysis_model="m", api_key="k",
        )
        with patch("httpx.Client", Client):
            with self.assertRaises(StructuredAnalysisError) as caught:
                provider.chat("system", [{"role": "user", "content": "ok"}])
        self.assertEqual(caught.exception.error_code, "cloudflare_challenge")
        self.assertEqual(captured["headers"]["User-Agent"], "PsychDeep-API/1")


if __name__ == "__main__":
    unittest.main()

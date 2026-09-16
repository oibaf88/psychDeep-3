"""Shared gateway tests: every API key here is a disposable fixture."""
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from app.services import personal_llm
from app.services.llm import build_provider
from app.routers.personal_llm import PersonalLLMSettingsIn


class MemorySession:
    def __init__(self):
        self.rows = {}
        self.info = {}

    def get(self, _model, user_id):
        return self.rows.get(user_id)

    def add(self, row):
        self.rows[row.user_id] = row

    def commit(self):
        pass

    def delete(self, row):
        del self.rows[row.user_id]


def settings(**overrides):
    values = dict(
        model_local_cf_access_host="ai.bfab.io",
        model_local_base_url="https://ai.bfab.io/v1",
        model_local_cf_access_required=True,
        model_local_cf_access_client_id="shared-access-id",
        model_local_cf_access_client_secret="shared-access-secret",
        model_local_api_key="shared-lm-bearer",
        model_local_chat_model="test-model",
        model_local_analysis_model="test-model",
        model_local_copilot_model="test-model",
        model_local_max_tokens=2048,
        model_local_timeout_seconds=30,
        local_chat_model="test-model",
        local_analysis_model="test-model",
        local_copilot_model="test-model",
        model_allow_commercial=True,
        anthropic_api_key="server-anthropic-test-key",
        anthropic_chat_model="claude-test",
        anthropic_analysis_model="claude-test",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def payload(provider="openai_compatible", model="test-model"):
    return SimpleNamespace(
        provider=provider, chat_model=model, analysis_model=model,
        copilot_model="", max_tokens=1024, timeout_seconds=30,
    )


class SharedGatewayTests(unittest.TestCase):
    def setUp(self):
        self.db = MemorySession()
        self.a, self.b = uuid.uuid4(), uuid.uuid4()
        self.fake_settings = patch.object(personal_llm, "get_settings", return_value=settings())
        self.mock_settings = self.fake_settings.start()

    def tearDown(self):
        self.fake_settings.stop()

    def test_new_accounts_use_local_without_supplying_any_secret(self):
        status = personal_llm.status(self.db, self.a)
        self.assertFalse(status["configured"])
        self.assertTrue(status["local_available"])
        self.assertEqual(status["provider"], "openai_compatible")
        self.assertNotIn("shared-access-secret", str(status))
        self.assertNotIn("shared-lm-bearer", str(status))
        config = personal_llm.resolve(self.db, self.a)
        headers = build_provider(config)._headers()
        self.assertEqual(headers["Authorization"], "Bearer shared-lm-bearer")
        self.assertEqual(headers["CF-Access-Client-Id"], "shared-access-id")
        self.assertEqual(headers["CF-Access-Client-Secret"], "shared-access-secret")
        self.assertNotIn("shared-lm-bearer", repr(config))
        self.assertNotIn("shared-access-secret", repr(config))

    def test_personal_choice_does_not_change_other_accounts_credentials_or_provider(self):
        personal_llm.save(self.db, self.a, payload(model="old-stale-model"))
        personal_llm.save(self.db, self.b, payload(provider="anthropic", model="claude-test"))
        # A previously saved model ID must never override operator settings.
        self.db.rows[self.a].chat_model = "obsolete-model"
        self.db.rows[self.a].analysis_model = "obsolete-model"
        a = personal_llm.resolve(self.db, self.a)
        b = personal_llm.resolve(self.db, self.b)
        self.assertEqual((a.provider, a.chat_model), ("openai_compatible", "test-model"))
        self.assertEqual(personal_llm.status(self.db, self.a)["chat_model"], "test-model")
        self.assertEqual(b.provider, "anthropic")
        self.assertEqual(a.api_key, "shared-lm-bearer")
        self.assertNotIn("shared-access-secret", str(personal_llm.status(self.db, self.b)))
        self.assertEqual(personal_llm.resolve(self.db, uuid.uuid4()).provider, "openai_compatible")

    def test_missing_either_auth_layer_denies_local_inference(self):
        for field in (
            "model_local_cf_access_client_id",
            "model_local_cf_access_client_secret",
            "model_local_api_key",
            "model_local_cf_access_host",
        ):
            with self.subTest(field=field):
                self.mock_settings.return_value = settings(**{field: ""})
                self.assertFalse(personal_llm.shared_ready())
                with self.assertRaises(RuntimeError):
                    personal_llm.resolve(self.db, self.a)
                with self.assertRaises(RuntimeError):
                    personal_llm.save(self.db, self.a, payload())
        self.assertEqual(self.db.rows, {})

    def test_access_policy_must_be_required_and_endpoint_pinned(self):
        for values in (
            {"model_local_cf_access_required": False},
            {"model_local_base_url": "http://ai.bfab.io/v1"},
            {"model_local_base_url": "https://evil.example/v1"},
            {"model_local_base_url": "https://ai.bfab.io/v1?token=oops"},
            {"model_local_base_url": "https://user@ai.bfab.io/v1"},
        ):
            with self.subTest(values=values):
                self.mock_settings.return_value = settings(**values)
                self.assertFalse(personal_llm.shared_ready())
                with self.assertRaises((RuntimeError, ValueError)):
                    personal_llm.resolve(self.db, self.a)

    def test_personal_api_rejects_secret_submission_and_untrusted_url(self):
        safe = dict(provider="openai_compatible", chat_model="test-model", analysis_model="test-model")
        for extra in ("cf_client_id", "cf_client_secret", "lm_api_key", "base_url", "tunnel_token"):
            with self.subTest(extra=extra):
                with self.assertRaises(ValidationError):
                    PersonalLLMSettingsIn.model_validate({**safe, extra: "attacker-value"})

    def test_legacy_secrets_are_ignored_then_retired_on_account_update(self):
        personal_llm.save(self.db, self.a, payload())
        row = self.db.rows[self.a]
        row.lm_api_key_encrypted = "legacy-lm-ciphertext"
        row.cf_client_id_encrypted = "legacy-id-ciphertext"
        row.cf_client_secret_encrypted = "legacy-secret-ciphertext"
        self.assertEqual(personal_llm.resolve(self.db, self.a).api_key, "shared-lm-bearer")
        personal_llm.save(self.db, self.a, payload())
        self.assertIsNone(row.lm_api_key_encrypted)
        self.assertIsNone(row.cf_client_id_encrypted)
        self.assertIsNone(row.cf_client_secret_encrypted)

    def test_no_anthropic_fallback_when_shared_local_not_ready(self):
        self.mock_settings.return_value = settings(model_local_api_key="")
        with self.assertRaises(RuntimeError):
            personal_llm.resolve(self.db, self.a)
        self.assertEqual(personal_llm.status(self.db, self.a)["provider"], "openai_compatible")


if __name__ == "__main__":
    unittest.main()

"""Disposable secrets only: test shared Access and isolated user LM Studio keys."""
import os
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.services import personal_llm
from app.services.llm import build_provider
from app.services.local_model_catalog import Catalog, LocalModel
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
        model_local_api_key="obsolete-shared-lm-token-must-not-be-used",
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
        anthropic_copilot_model="",
        openai_api_key="test-openai-key",
        openai_chat_model="test-openai-model",
        openai_analysis_model="test-openai-model",
        openai_copilot_model="test-openai-model",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def payload(provider="openai_compatible", model="test-model", key=None):
    return SimpleNamespace(
        provider=provider, chat_model=model, analysis_model=model,
        copilot_model="", max_tokens=1024, timeout_seconds=30, lm_api_key=key,
    )


class PersonalGatewayTests(unittest.TestCase):
    def setUp(self):
        self.db = MemorySession()
        self.a, self.b = uuid.uuid4(), uuid.uuid4()
        self.env_patch = patch.dict(os.environ, {"LLM_USER_CREDENTIALS_KEY": Fernet.generate_key().decode()})
        self.env_patch.start()
        self.fake_settings = patch.object(personal_llm, "get_settings", return_value=settings())
        self.mock_settings = self.fake_settings.start()
        # Keep unit tests off the live tunnel. An unreachable catalog preserves
        # the id the account stored.
        self.catalog_patch = patch.object(
            personal_llm, "fetch_catalog",
            return_value=Catalog((LocalModel("loaded-on-computer", True),), True),
        )
        self.catalog_patch.start()

    def tearDown(self):
        self.catalog_patch.stop()
        self.fake_settings.stop()
        self.env_patch.stop()

    def test_new_accounts_must_supply_their_own_key_no_shared_fallback(self):
        state = personal_llm.status(self.db, self.a)
        self.assertTrue(state["local_available"])
        self.assertFalse(state["lm_api_key_configured"])
        self.assertEqual(state["provider"], "openai_compatible")
        with self.assertRaisesRegex(RuntimeError, "API key personal"):
            personal_llm.resolve(self.db, self.a)
        with self.assertRaisesRegex(ValueError, "API key personal"):
            personal_llm.save(self.db, self.a, payload())
        self.assertFalse(self.db.rows)

    def test_two_accounts_have_distinct_bearer_and_shared_cloudflare_headers(self):
        personal_llm.save(self.db, self.a, payload(key="lm-key-alice"))
        personal_llm.save(self.db, self.b, payload(key="lm-key-bob"))
        a = personal_llm.resolve(self.db, self.a)
        b = personal_llm.resolve(self.db, self.b)
        self.assertEqual(build_provider(a)._headers()["Authorization"], "Bearer lm-key-alice")
        self.assertEqual(build_provider(b)._headers()["Authorization"], "Bearer lm-key-bob")
        for resolved in (a, b):
            headers = build_provider(resolved)._headers()
            self.assertEqual(headers["CF-Access-Client-Id"], "shared-access-id")
            self.assertEqual(headers["CF-Access-Client-Secret"], "shared-access-secret")
            self.assertNotIn("obsolete-shared-lm-token-must-not-be-used", str(headers))
            self.assertNotIn(resolved.api_key, repr(resolved))
            self.assertNotIn("shared-access-secret", repr(resolved))
        self.assertNotIn("lm-key-alice", self.db.rows[self.a].lm_api_key_encrypted)
        self.assertNotIn("lm-key-bob", self.db.rows[self.b].lm_api_key_encrypted)
        self.assertNotEqual(self.db.rows[self.a].lm_api_key_encrypted, self.db.rows[self.b].lm_api_key_encrypted)
        self.assertNotIn("lm-key-alice", str(personal_llm.status(self.db, self.a)))
        self.assertNotIn("shared-access-secret", str(personal_llm.status(self.db, self.b)))
        self.assertTrue(personal_llm.status(self.db, self.a)["lm_api_key_configured"])

    def test_rotate_preserve_and_revoke_only_current_account(self):
        personal_llm.save(self.db, self.a, payload(key="alice-original"))
        personal_llm.save(self.db, self.b, payload(key="bob-key"))
        ciphertext = self.db.rows[self.a].lm_api_key_encrypted
        personal_llm.save(self.db, self.a, payload(key=None))
        self.assertEqual(self.db.rows[self.a].lm_api_key_encrypted, ciphertext)
        personal_llm.save(self.db, self.a, payload(key="alice-rotated"))
        self.assertEqual(personal_llm.resolve(self.db, self.a).api_key, "alice-rotated")
        self.assertEqual(personal_llm.resolve(self.db, self.b).api_key, "bob-key")
        # Revocation while switching to Anthropic must not remove Bob's key.
        personal_llm.save(self.db, self.a, payload(provider="anthropic", model="claude-test", key=""))
        self.assertFalse(personal_llm.status(self.db, self.a)["lm_api_key_configured"])
        self.assertEqual(personal_llm.resolve(self.db, self.a).provider, "anthropic")
        self.assertEqual(personal_llm.resolve(self.db, self.b).api_key, "bob-key")
        with self.assertRaises(ValueError):
            personal_llm.save(self.db, self.a, payload())

    def test_anthropic_selection_preserves_personal_lm_key(self):
        personal_llm.save(self.db, self.a, payload(key="alice-key"))
        personal_llm.save(self.db, self.a, payload(provider="anthropic", model="claude-test"))
        self.assertTrue(personal_llm.status(self.db, self.a)["lm_api_key_configured"])
        self.assertEqual(personal_llm.resolve(self.db, self.a).provider, "anthropic")
        personal_llm.save(self.db, self.a, payload())
        self.assertEqual(personal_llm.resolve(self.db, self.a).api_key, "alice-key")

    def test_missing_access_credentials_blocks_both_users_without_erasing_keys(self):
        personal_llm.save(self.db, self.a, payload(key="alice-key"))
        for field in ("model_local_cf_access_client_id", "model_local_cf_access_client_secret", "model_local_cf_access_host"):
            with self.subTest(field=field):
                self.mock_settings.return_value = settings(**{field: ""})
                self.assertFalse(personal_llm.shared_ready())
                with self.assertRaises((RuntimeError, ValueError)):
                    personal_llm.resolve(self.db, self.a)
        self.mock_settings.return_value = settings()
        self.assertEqual(personal_llm.resolve(self.db, self.a).api_key, "alice-key")

    def test_requires_access_and_pins_endpoint(self):
        personal_llm.save(self.db, self.a, payload(key="alice-key"))
        for override in (
            {"model_local_cf_access_required": False},
            {"model_local_base_url": "http://ai.bfab.io/v1"},
            {"model_local_base_url": "https://evil.example/v1"},
            {"model_local_base_url": "https://ai.bfab.io/v1?token=oops"},
            {"model_local_base_url": "https://user@ai.bfab.io/v1"},
        ):
            with self.subTest(override=override):
                self.mock_settings.return_value = settings(**override)
                self.assertFalse(personal_llm.shared_ready())
                with self.assertRaises((RuntimeError, ValueError)):
                    personal_llm.resolve(self.db, self.a)

    def test_old_personal_access_secrets_never_used_and_cleared_on_save(self):
        personal_llm.save(self.db, self.a, payload(key="alice-key"))
        row = self.db.rows[self.a]
        row.cf_client_id_encrypted = "obsolete-personal-id"
        row.cf_client_secret_encrypted = "obsolete-personal-secret"
        headers = build_provider(personal_llm.resolve(self.db, self.a))._headers()
        self.assertEqual(headers["CF-Access-Client-Id"], "shared-access-id")
        self.assertNotIn("obsolete-personal-secret", str(headers))
        personal_llm.save(self.db, self.a, payload())
        self.assertIsNone(row.cf_client_id_encrypted)
        self.assertIsNone(row.cf_client_secret_encrypted)
        self.assertEqual(personal_llm.resolve(self.db, self.a).api_key, "alice-key")

    def test_cipher_missing_or_rotated_fails_closed_and_never_uses_shared_key(self):
        personal_llm.save(self.db, self.a, payload(key="alice-key"))
        with patch.dict(os.environ, {"LLM_USER_CREDENTIALS_KEY": ""}):
            with self.assertRaises(RuntimeError):
                personal_llm.resolve(self.db, self.a)
            with self.assertRaises(RuntimeError):
                personal_llm.save(self.db, self.b, payload(key="bob-key"))
        with patch.dict(os.environ, {"LLM_USER_CREDENTIALS_KEY": Fernet.generate_key().decode()}):
            with self.assertRaises(RuntimeError):
                personal_llm.resolve(self.db, self.a)
        self.assertEqual(personal_llm.resolve(self.db, self.a).api_key, "alice-key")

    def test_api_accepts_only_personal_lm_token_not_access_or_endpoint(self):
        safe = dict(provider="openai_compatible", chat_model="test-model", analysis_model="test-model", lm_api_key="test")
        self.assertEqual(PersonalLLMSettingsIn.model_validate(safe).lm_api_key, "test")
        for extra in ("cf_client_id", "cf_client_secret", "base_url", "tunnel_token"):
            with self.subTest(extra=extra):
                with self.assertRaises(ValidationError):
                    PersonalLLMSettingsIn.model_validate({**safe, extra: "attacker-value"})
        with self.assertRaises(ValidationError):
            PersonalLLMSettingsIn.model_validate({**safe, "lm_api_key": "x" * 8193})

    def test_stale_stored_model_is_replaced_by_the_loaded_one(self):
        personal_llm.save(self.db, self.a, payload(key="alice-key"))
        self.db.rows[self.a].chat_model = "gemma-2-2b-it"
        catalog = Catalog((LocalModel("loaded-model", True), LocalModel("other-model", False)), True)
        with patch.object(personal_llm, "fetch_catalog", return_value=catalog):
            resolved = personal_llm.resolve(self.db, self.a)
            state = personal_llm.status(self.db, self.a)
        self.assertEqual(resolved.chat_model, "loaded-model")
        self.assertEqual(resolved.analysis_model, "loaded-model")
        self.assertEqual(state["chat_model"], "")
        self.assertEqual(state["effective_local_model"], "loaded-model")
        self.assertEqual(state["default_local_chat_model"], "loaded-model")
        self.assertEqual(state["local_models"][0]["id"], "loaded-model")
        self.assertNotIn("gemma-2-2b-it", str(state["local_models"]))

    def test_a_requested_model_id_is_discarded_for_the_loaded_one(self):
        personal_llm.save(self.db, self.a, payload(model="kept-model", key="alice-key"))
        self.assertEqual(self.db.rows[self.a].chat_model, "")
        self.assertEqual(self.db.rows[self.a].analysis_model, "")
        catalog = Catalog((LocalModel("kept-model", False), LocalModel("loaded-model", True)), True)
        with patch.object(personal_llm, "fetch_catalog", return_value=catalog):
            resolved = personal_llm.resolve(self.db, self.a)
        self.assertEqual(resolved.chat_model, "loaded-model")
        self.assertEqual(resolved.analysis_model, "loaded-model")

    def test_commercial_providers_ignore_a_client_model_name(self):
        personal_llm.save(self.db, self.a, payload(provider="anthropic", model="not-a-choice", key="alice-key"))
        resolved = personal_llm.resolve(self.db, self.a)
        self.assertEqual(resolved.provider, "anthropic")
        self.assertEqual(resolved.chat_model, "claude-test")
        personal_llm.save(self.db, self.a, payload(provider="openai", model="also-not-a-choice"))
        resolved = personal_llm.resolve(self.db, self.a)
        self.assertEqual(resolved.provider, "openai")
        self.assertEqual(resolved.chat_model, "test-openai-model")

    def test_several_models_and_no_choice_does_not_invent_one(self):
        personal_llm.save(self.db, self.a, payload(key="alice-key"))
        self.db.rows[self.a].chat_model = "gemma-2-2b-it"
        catalog = Catalog((LocalModel("one", False), LocalModel("two", False)), True)
        with patch.object(personal_llm, "fetch_catalog", return_value=catalog):
            with self.assertRaises(personal_llm.LocalModelUnavailable):
                personal_llm.resolve(self.db, self.a)
            self.assertEqual(personal_llm.status(self.db, self.a)["chat_model"], "")

    def test_rejects_invalid_new_token_without_changing_other_accounts(self):
        personal_llm.save(self.db, self.b, payload(key="bob-key"))
        with self.assertRaises(ValueError):
            personal_llm.save(self.db, self.a, payload(key="not-valid\r\nheader"))
        self.assertEqual(personal_llm.resolve(self.db, self.b).api_key, "bob-key")
        self.assertNotIn(self.a, self.db.rows)


class PersonalSettingsAuthorizationTests(unittest.TestCase):
    def test_every_personal_route_requires_admin_clinical(self):
        import inspect

        from fastapi.params import Depends

        from app.routers import personal_llm as routes
        from app.security import require_admin

        for endpoint in (
            routes.read_personal_settings,
            routes.update_personal_settings,
            routes.delete_personal_settings,
            routes.test_personal_settings,
        ):
            dependency = inspect.signature(endpoint).parameters["user"].default
            self.assertIsInstance(dependency, Depends)
            self.assertIs(dependency.dependency, require_admin)


if __name__ == "__main__":
    unittest.main()

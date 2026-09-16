"""Per-account LLM isolation tests. All credentials are disposable test values."""
import os
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.fernet import Fernet

from app.services import personal_llm
from app.services.llm import build_provider


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


def settings():
    return SimpleNamespace(
        model_local_cf_access_host="ai.bfab.io",
        local_base_url="https://ai.bfab.io/v1",
        anthropic_chat_model="claude-test",
        anthropic_analysis_model="claude-test",
        model_allow_commercial=True,
        anthropic_api_key="server-anthropic-test-key",
    )


def payload(lm, cf_id, cf_secret, *, provider="openai_compatible", url="https://ai.bfab.io/v1"):
    return SimpleNamespace(
        provider=provider, base_url=url, chat_model="test-model",
        analysis_model="test-model", copilot_model="", max_tokens=1024,
        timeout_seconds=30, lm_api_key=lm, cf_client_id=cf_id,
        cf_client_secret=cf_secret,
    )


class PersonalSettingsTests(unittest.TestCase):
    def setUp(self):
        self.db = MemorySession()
        self.a, self.b = uuid.uuid4(), uuid.uuid4()
        self.env = patch.dict(os.environ, {"LLM_USER_CREDENTIALS_KEY": Fernet.generate_key().decode("ascii")})
        self.env.start()
        self.fake_settings = patch.object(personal_llm, "get_settings", return_value=settings())
        self.fake_settings.start()

    def tearDown(self):
        self.fake_settings.stop()
        self.env.stop()

    def test_each_user_has_independent_encrypted_secrets_and_model_choice(self):
        first = personal_llm.save(self.db, self.a, payload("lm-a", "cf-a", "secret-a"))
        second = personal_llm.save(self.db, self.b, payload("lm-b", "cf-b", "secret-b"))
        self.assertTrue(first["lm_api_key_configured"])
        self.assertTrue(second["cf_client_secret_configured"])
        self.assertNotIn("secret-a", str(first))
        self.assertNotIn("lm-b", str(second))
        self.assertNotIn("lm-a", str(self.db.rows[self.a].lm_api_key_encrypted))
        self.assertNotIn("cf-a", str(self.db.rows[self.a].cf_client_id_encrypted))
        self.assertNotEqual(self.db.rows[self.a].lm_api_key_encrypted, self.db.rows[self.b].lm_api_key_encrypted)
        self.assertEqual(personal_llm.resolve(self.db, self.a).api_key, "lm-a")
        self.assertEqual(personal_llm.resolve(self.db, self.b).access_client_secret, "secret-b")
        self.assertEqual(personal_llm.status(self.db, self.a)["provider"], "openai_compatible")

    def test_both_auth_layers_present_without_leaking_to_other_account(self):
        personal_llm.save(self.db, self.a, payload("lm-a", "cf-a", "secret-a"))
        personal_llm.save(self.db, self.b, payload("lm-b", "cf-b", "secret-b"))
        headers_a = build_provider(personal_llm.resolve(self.db, self.a))._headers()
        headers_b = build_provider(personal_llm.resolve(self.db, self.b))._headers()
        self.assertEqual(headers_a["Authorization"], "Bearer lm-a")
        self.assertEqual(headers_a["CF-Access-Client-Id"], "cf-a")
        self.assertEqual(headers_a["CF-Access-Client-Secret"], "secret-a")
        self.assertEqual(headers_b["Authorization"], "Bearer lm-b")
        self.assertEqual(headers_b["CF-Access-Client-Secret"], "secret-b")
        self.assertNotIn("secret-a", str(headers_b))

    def test_local_selection_refuses_missing_any_credential(self):
        for lm, cid, secret in ((None, "id", "secret"), ("lm", None, "secret"), ("lm", "id", None)):
            with self.subTest(lm=bool(lm), cid=bool(cid), secret=bool(secret)):
                with self.assertRaises(ValueError):
                    personal_llm.save(self.db, self.a, payload(lm, cid, secret))

    def test_non_approved_http_and_host_are_rejected_before_saving(self):
        for url in ("http://ai.bfab.io/v1", "https://evil.example/v1", "https://ai.bfab.io:8080/v1", "https://user@ai.bfab.io/v1", "https://ai.bfab.io/v1?token=x"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    personal_llm.save(self.db, self.a, payload("lm", "id", "secret", url=url))
        self.assertEqual(self.db.rows, {})

    def test_secret_rotation_and_retention_and_fail_closed_without_master_key(self):
        personal_llm.save(self.db, self.a, payload("old-lm", "old-id", "old-secret"))
        personal_llm.save(self.db, self.a, payload("new-lm", None, None))
        current = personal_llm.resolve(self.db, self.a)
        self.assertEqual((current.api_key, current.access_client_id, current.access_client_secret),
                         ("new-lm", "old-id", "old-secret"))
        with patch.dict(os.environ, {"LLM_USER_CREDENTIALS_KEY": ""}):
            with self.assertRaises(RuntimeError):
                personal_llm.resolve(self.db, self.a)

    def test_personal_anthropic_selection_keeps_other_users_on_local(self):
        personal_llm.save(self.db, self.a, payload("lm-a", "cf-a", "secret-a"))
        personal_llm.save(self.db, self.b, payload(None, None, None, provider="anthropic"))
        self.assertEqual(personal_llm.resolve(self.db, self.a).provider, "openai_compatible")
        self.assertEqual(personal_llm.resolve(self.db, self.b).provider, "anthropic")


if __name__ == "__main__":
    unittest.main()

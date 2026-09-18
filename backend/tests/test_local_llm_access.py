"""Local LM Studio use requires a PsychDeep session and clinical-manager approval."""
import inspect
import unittest
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.params import Depends

from app.models import AuditLog, User
from app.routers import admin_users
from app.security import require_admin
from app.services import local_llm_access
from app.services.llm import get_llm_provider
from app.services.local_llm_access import LocalLlmAccessDenied
from tests.test_admin_users import _FakeSession, _user


class LocalLlmAccessPolicyTest(unittest.TestCase):
    def test_anonymous_and_inactive_accounts_are_denied(self):
        with self.assertRaisesRegex(LocalLlmAccessDenied, "sesión activa"):
            local_llm_access.assert_can_use_local_llm(None)
        inactive = _user("patient", email="p@example.com")
        inactive.is_active = False
        with self.assertRaisesRegex(LocalLlmAccessDenied, "no está activa"):
            local_llm_access.assert_can_use_local_llm(inactive)

    def test_patients_need_explicit_manager_approval(self):
        patient = _user("patient", email="p@example.com")
        self.assertFalse(local_llm_access.is_usable(patient))
        with self.assertRaisesRegex(LocalLlmAccessDenied, "administrador clínico"):
            local_llm_access.assert_can_use_local_llm(patient)
        patient.local_llm_approved = True
        local_llm_access.assert_can_use_local_llm(patient)
        self.assertEqual(local_llm_access.public_status(patient)["local_llm_access"], "approved")

    def test_clinical_manager_is_usable_without_the_flag(self):
        admin = _user("admin_clinical", email="admin@example.com")
        admin.local_llm_approved = False
        local_llm_access.assert_can_use_local_llm(admin)
        self.assertTrue(local_llm_access.public_status(admin)["local_llm_usable"])
        self.assertEqual(local_llm_access.public_status(admin)["local_llm_access"], "manager")


class LocalLlmProviderGateTest(unittest.TestCase):
    def test_unauthenticated_local_provider_fails_closed(self):
        config = SimpleNamespace(
            provider="openai_compatible",
            base_url="https://ai.bfab.io/v1",
            chat_model="m",
            analysis_model="m",
            copilot_model="m",
            api_key="k",
            max_tokens=256,
            timeout_seconds=10,
            explicit_max_tokens=256,
        )
        db = SimpleNamespace(info={}, get=lambda *_args: None)
        with patch("app.services.personal_resolution.personal_mode_enabled", return_value=False), patch(
            "app.services.llm_config.resolve", return_value=config
        ):
            with self.assertRaisesRegex(LocalLlmAccessDenied, "sesión activa"):
                get_llm_provider(db)

    def test_approved_patient_reaches_provider_builder(self):
        patient = _user("patient", email="p@example.com")
        patient.local_llm_approved = True
        config = SimpleNamespace(
            provider="openai_compatible",
            base_url="http://host.docker.internal:1234/v1",
            chat_model="m",
            analysis_model="m",
            copilot_model="m",
            api_key="k",
            max_tokens=256,
            timeout_seconds=10,
            explicit_max_tokens=256,
        )
        db = SimpleNamespace(
            info={"authenticated_user_id": patient.id},
            get=lambda model, key: patient if key == patient.id else None,
        )
        sentinel = object()
        with patch("app.services.personal_resolution.personal_mode_enabled", return_value=False), patch(
            "app.services.llm_config.resolve", return_value=config
        ), patch("app.services.llm.build_provider", return_value=sentinel) as built:
            self.assertIs(get_llm_provider(db), sentinel)
            built.assert_called_once_with(config)

    def test_anthropic_does_not_require_local_approval(self):
        patient = _user("patient", email="p@example.com")
        config = SimpleNamespace(
            provider="anthropic",
            chat_model="claude-test",
            analysis_model="claude-test",
            copilot_model="",
            explicit_max_tokens=256,
        )
        db = SimpleNamespace(info={"authenticated_user_id": patient.id}, get=lambda *_args: patient)
        sentinel = object()
        with patch("app.services.personal_resolution.personal_mode_enabled", return_value=False), patch(
            "app.services.llm_config.resolve", return_value=config
        ), patch("app.services.llm.build_provider", return_value=sentinel):
            self.assertIs(get_llm_provider(db), sentinel)


class AdminLocalLlmEndpointTest(unittest.TestCase):
    def test_new_endpoint_requires_admin_clinical(self):
        dependency = inspect.signature(admin_users.set_local_llm_access).parameters["admin"].default
        self.assertIsInstance(dependency, Depends)
        self.assertIs(dependency.dependency, require_admin)

    def test_manager_can_approve_and_withdraw_patient_access(self):
        admin = _user("admin_clinical", email="admin@example.com")
        patient = _user("patient", email="p@example.com")
        db = _FakeSession(users=[admin, patient])

        granted = admin_users.set_local_llm_access(
            patient.id,
            admin_users.AdminLocalLlmAccessUpdate(approved=True),
            db=db,
            admin=admin,
        )
        self.assertTrue(patient.local_llm_approved)
        self.assertEqual(granted.local_llm_access, "approved")
        self.assertTrue(granted.local_llm_usable)
        self.assertTrue(
            any(
                isinstance(obj, AuditLog) and obj.action == "local_llm_access_granted"
                for obj in db.added
            )
        )

        withdrawn = admin_users.set_local_llm_access(
            patient.id,
            admin_users.AdminLocalLlmAccessUpdate(approved=False),
            db=db,
            admin=admin,
        )
        self.assertFalse(patient.local_llm_approved)
        self.assertEqual(withdrawn.local_llm_access, "pending")

    def test_cannot_toggle_manager_or_revoked_account(self):
        admin = _user("admin_clinical", email="admin@example.com")
        other_admin = _user("admin_clinical", email="other@example.com")
        revoked = _user("therapist", email="t@example.com")
        revoked.is_active = False
        db = _FakeSession(users=[admin, other_admin, revoked])

        with self.assertRaises(Exception) as manager_denied:
            admin_users.set_local_llm_access(
                other_admin.id,
                admin_users.AdminLocalLlmAccessUpdate(approved=True),
                db=db,
                admin=admin,
            )
        self.assertIn("administrador clínico", str(manager_denied.exception.detail))

        with self.assertRaises(Exception) as revoked_denied:
            admin_users.set_local_llm_access(
                revoked.id,
                admin_users.AdminLocalLlmAccessUpdate(approved=True),
                db=db,
                admin=admin,
            )
        self.assertIn("revocada", str(revoked_denied.exception.detail))

    def test_revoking_account_clears_local_model_approval(self):
        admin = _user("admin_clinical", email="admin@example.com")
        therapist = _user("therapist", email="t@example.com")
        therapist.local_llm_approved = True
        db = _FakeSession(users=[admin, therapist])
        admin_users.revoke_user_access(therapist.id, db=db, admin=admin)
        self.assertFalse(therapist.local_llm_approved)
        self.assertFalse(therapist.is_active)

"""Account regressions against an isolated, in-memory SQL database."""
from datetime import datetime, timedelta
import unittest
import uuid

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import AuditLog, Consent, PasswordResetToken, SafetyPlan, User
from app.routers import admin_users, auth
from app.schemas import AccountProfileUpdate, LoginRequest, PasswordChangeRequest, PasswordResetConfirm, UserCreate
from app.security import hash_password, verify_password


class AccountFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = "AccountPassword123!"
        cls.password_hash = hash_password(cls.password)

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for model in (User, Consent, SafetyPlan, PasswordResetToken, AuditLog):
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

    def user(self, email="Legacy.User@example.com", **values):
        user = User(email=email, hashed_password=self.password_hash, display_name="Ari", **values)
        self.db.add(user)
        self.db.commit()
        return user

    def reset_token(self, user):
        token = PasswordResetToken(user_id=user.id, token=str(uuid.uuid4()), expires_at=datetime.utcnow() + timedelta(hours=1))
        self.db.add(token)
        self.db.commit()
        return token

    def test_login_accepts_changed_email_casing_for_legacy_account(self):
        user = self.user()
        result = auth.login(LoginRequest(email="LEGACY.USER@EXAMPLE.COM", password=self.password), self.db)
        self.assertEqual(result.user.id, user.id)

    def test_signup_cannot_duplicate_legacy_email_with_different_case(self):
        self.user()
        with self.assertRaises(HTTPException) as caught:
            auth.register(UserCreate(email="legacy.user@example.com", password=self.password, display_name="Other"), self.db)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.db.query(User).count(), 1)

    def test_signup_normalizes_email_and_display_name(self):
        result = auth.register(UserCreate(email="NEW.USER@EXAMPLE.COM", password=self.password, display_name="  Ari  "), self.db)
        self.assertEqual(result.user.email, "new.user@example.com")
        self.assertEqual(result.user.display_name, "Ari")

    def test_provision_cannot_duplicate_legacy_email_with_different_case(self):
        self.user()
        admin = self.user("admin@example.com", role="admin_clinical")
        with self.assertRaises(HTTPException) as caught:
            admin_users.provision_user(admin_users.AdminUserCreate(email="legacy.user@example.com", password=self.password, display_name="Other"), self.db, admin)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(self.db.query(User).count(), 2)

    def test_blank_and_oversized_signup_names_are_rejected_before_database(self):
        for name in ("   ", "x" * 256):
            with self.subTest(name_length=len(name)), self.assertRaises(ValidationError):
                UserCreate(email="new@example.com", password=self.password, display_name=name)

    def test_profile_supports_a_name_without_surname(self):
        user = self.user(first_name="Ari", last_name="Old surname")
        result = auth.update_my_profile(AccountProfileUpdate(first_name="Ari", last_name=""), self.db, user)
        self.assertIsNone(result.last_name)
        self.assertEqual(result.display_name, "Ari")

    def test_profile_clearing_surname_does_not_leave_the_old_display_name(self):
        user = self.user(last_name="Surname")
        result = auth.update_my_profile(AccountProfileUpdate(first_name="New", last_name="   "), self.db, user)
        self.assertEqual(result.display_name, "New")

    def test_password_change_invalidates_pending_reset_links(self):
        user = self.user()
        token = self.reset_token(user)
        auth.change_password(PasswordChangeRequest(current_password=self.password, new_password="NewAccountPassword123!"), self.db, user)
        self.db.refresh(token)
        self.assertTrue(token.is_used)
        with self.assertRaises(HTTPException) as caught:
            auth.password_reset_confirm(PasswordResetConfirm(token=token.token, new_password="UnwantedPassword123!"), self.db)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertTrue(verify_password("NewAccountPassword123!", user.hashed_password))

    def test_password_reset_invalidates_other_pending_reset_links(self):
        user = self.user()
        first = self.reset_token(user)
        second = self.reset_token(user)
        auth.password_reset_confirm(PasswordResetConfirm(token=first.token, new_password="NewAccountPassword123!"), self.db)
        self.db.refresh(second)
        self.assertTrue(second.is_used)
        with self.assertRaises(HTTPException):
            auth.password_reset_confirm(PasswordResetConfirm(token=second.token, new_password="UnwantedPassword123!"), self.db)


if __name__ == "__main__":
    unittest.main()

import unittest
import uuid
from unittest.mock import MagicMock, patch

import bcrypt
from fastapi import HTTPException, status
from jose import jwt

from app.config import get_settings
from app.models import User
from app.security import (
    _BCRYPT_MAX_BYTES,
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    require_patient,
    require_professional,
    require_roles,
    verify_password,
)

settings = get_settings()


class PasswordHashingTests(unittest.TestCase):
    def test_hash_password_returns_hashed_string(self):
        password = "my_secure_password"
        hashed = hash_password(password)

        self.assertIsInstance(hashed, str)
        self.assertNotEqual(password, hashed)
        self.assertTrue(hashed.startswith("$2b$") or hashed.startswith("$2a$"))

    def test_hash_password_verifiable_with_verify_password(self):
        hashed = hash_password("correct_password")

        self.assertTrue(verify_password("correct_password", hashed))
        self.assertFalse(verify_password("wrong_password", hashed))

    def test_hash_password_rejects_new_passwords_above_bcrypt_limit(self):
        # New credentials must never silently collapse to the first 72 bytes.
        with self.assertRaises(ValueError):
            hash_password("a" * (_BCRYPT_MAX_BYTES + 1))

    def test_hash_password_rejects_short_password(self):
        with self.assertRaises(ValueError):
            hash_password("")

    def test_hash_password_handles_unicode_characters(self):
        password = "🔒contraseña_123!_€"
        hashed = hash_password(password)

        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("🔒contraseña_123!_$", hashed))

    @patch("bcrypt.hashpw")
    @patch("bcrypt.gensalt")
    def test_hash_password_calls_bcrypt_with_full_valid_bytes(self, mock_gensalt, mock_hashpw):
        mock_gensalt.return_value = b"$2b$12$fakegensaltstringhere"
        mock_hashpw.return_value = b"$2b$12$fakehashedpasswordstring"

        password = "x" * 20
        result = hash_password(password)

        mock_gensalt.assert_called_once()
        mock_hashpw.assert_called_once_with(password.encode("utf-8"), mock_gensalt.return_value)
        self.assertEqual(result, "$2b$12$fakehashedpasswordstring")

    def test_verify_password_invalid_hash_variants_return_false(self):
        for invalid_hash in ("", "invalid_hash", "not_a_bcrypt_hash", "1234567890" * 3):
            with self.subTest(invalid_hash=invalid_hash):
                self.assertFalse(verify_password("MySecurePassword123!", invalid_hash))

    def test_verify_password_invalid_types(self):
        self.assertFalse(verify_password("MySecurePassword123!", None))
        self.assertFalse(verify_password(None, "invalid_hash"))
        self.assertFalse(verify_password(12345, "invalid_hash"))

    def test_verify_password_long_password_truncation(self):
        # Existing bcrypt hashes retain legacy verification compatibility.
        long_password = "a" * 100
        hashed = bcrypt.hashpw(long_password.encode("utf-8")[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()).decode("utf-8")
        self.assertTrue(verify_password(long_password, hashed))

        # Passwords sharing the first 72 bytes evaluate to True due to 72-byte truncation.
        self.assertTrue(verify_password("a" * 72 + "different_suffix", hashed))

        # A password differing within the first 72 bytes evaluates to False.
        self.assertFalse(verify_password("a" * 70 + "bb" + "a" * 28, hashed))


class CurrentUserTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.user_id = uuid.uuid4()
        self.user = User(id=self.user_id, email="test@example.com", role="patient", is_active=True)

    def _assert_unauthorized(self, token):
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=token, db=self.db)
        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(ctx.exception.detail, "Could not validate credentials")
        self.assertEqual(ctx.exception.headers, {"WWW-Authenticate": "Bearer"})

    def test_get_current_user_valid_token(self):
        token = create_access_token(self.user_id, role="patient")
        self.db.get.return_value = self.user

        self.assertEqual(get_current_user(token=token, db=self.db), self.user)
        self.db.get.assert_called_once_with(User, self.user_id)

    def test_get_current_user_malformed_token_raises_401(self):
        self._assert_unauthorized("invalid.jwt.token")
        self.db.get.assert_not_called()

    def test_get_current_user_tampered_signature_raises_401(self):
        token = create_access_token(self.user_id, role="patient")
        self._assert_unauthorized(token[:-5] + "XXXXX")

    def test_get_current_user_wrong_secret_raises_401(self):
        token = jwt.encode({"sub": str(self.user_id)}, "wrong_secret", algorithm=settings.jwt_algorithm)
        self._assert_unauthorized(token)
        self.db.get.assert_not_called()

    def test_get_current_user_missing_sub_claim_raises_401(self):
        token = jwt.encode({"role": "patient"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        self._assert_unauthorized(token)
        self.db.get.assert_not_called()

    def test_get_current_user_nonexistent_user_raises_401(self):
        self.db.get.return_value = None
        self._assert_unauthorized(create_access_token(self.user_id, role="patient"))

    def test_get_current_user_inactive_user_raises_401(self):
        self.user.is_active = False
        self.db.get.return_value = self.user
        self._assert_unauthorized(create_access_token(self.user_id, role="patient"))

    def test_auth_version_invalidates_pre_rotation_session(self):
        self.user.auth_version = 2
        self.db.get.return_value = self.user
        self._assert_unauthorized(create_access_token(self.user_id, role="patient", auth_version=1))


class RoleDependencyTests(unittest.TestCase):
    def test_require_roles_success(self):
        user = User(id=uuid.uuid4(), role="patient", is_active=True)
        self.assertEqual(require_roles("patient", "admin_clinical")(user=user), user)

    def test_require_roles_forbidden(self):
        user = MagicMock(spec=User, role="patient")
        with self.assertRaises(HTTPException) as ctx:
            require_roles("therapist", "admin_clinical")(user=user)

        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ctx.exception.detail, "Insufficient permissions")

    def test_require_role_helpers(self):
        user = User(id=uuid.uuid4(), is_active=True)
        user.role = "patient"
        self.assertEqual(require_patient(user=user), user)

        user.role = "therapist"
        self.assertEqual(require_professional(user=user), user)

        user.role = "admin_clinical"
        self.assertEqual(require_admin(user=user), user)


if __name__ == "__main__":
    unittest.main()

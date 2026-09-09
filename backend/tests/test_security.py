import unittest
from unittest.mock import patch
import bcrypt

from app.security import hash_password, verify_password, _BCRYPT_MAX_BYTES


class SecurityHashPasswordTest(unittest.TestCase):
    def test_hash_password_returns_hashed_string(self):
        password = "my_secure_password"
        hashed = hash_password(password)

        self.assertIsInstance(hashed, str)
        self.assertNotEqual(password, hashed)
        self.assertTrue(hashed.startswith("$2b$") or hashed.startswith("$2a$"))

    def test_hash_password_verifiable_with_verify_password(self):
        password = "correct_password"
        hashed = hash_password(password)

        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("wrong_password", hashed))

    def test_hash_password_rejects_new_passwords_above_bcrypt_limit(self):
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
        expected_bytes = password.encode("utf-8")
        mock_hashpw.assert_called_once_with(expected_bytes, mock_gensalt.return_value)
        self.assertEqual(result, "$2b$12$fakehashedpasswordstring")
import uuid
from unittest.mock import MagicMock

from fastapi import HTTPException, status

from app.security import hash_password, verify_password


class SecurityTests(unittest.TestCase):
    def test_verify_password_correct(self):
        plain_password = "MySecurePassword123!"
        hashed = hash_password(plain_password)
        self.assertTrue(verify_password(plain_password, hashed))

    def test_verify_password_incorrect(self):
        plain_password = "MySecurePassword123!"
        hashed = hash_password(plain_password)
        self.assertFalse(verify_password("WrongPassword123!", hashed))

    def test_verify_password_invalid_hash(self):
        self.assertFalse(verify_password("MySecurePassword123!", "invalid_hash"))
        self.assertFalse(verify_password("MySecurePassword123!", ""))
        self.assertFalse(verify_password("MySecurePassword123!", "not_a_bcrypt_hash"))

    def test_verify_password_invalid_types(self):
        self.assertFalse(verify_password("MySecurePassword123!", None))
        self.assertFalse(verify_password(None, "invalid_hash"))
        self.assertFalse(verify_password(12345, "invalid_hash"))

    def test_verify_password_long_password_truncation(self):
        # Existing bcrypt hashes retain legacy verification compatibility.
        long_password = "a" * 100
        hashed = bcrypt.hashpw(long_password.encode("utf-8")[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()).decode("utf-8")
        self.assertTrue(verify_password(long_password, hashed))

        # Passwords sharing the first 72 bytes should evaluate to True due to 72-byte truncation
        shared_prefix_pass = "a" * 72 + "different_suffix"
        self.assertTrue(verify_password(shared_prefix_pass, hashed))

        # Password differing within the first 72 bytes should evaluate to False
        different_pass = "a" * 70 + "bb" + "a" * 28
        self.assertFalse(verify_password(different_pass, hashed))
import uuid
from unittest.mock import MagicMock

from fastapi import HTTPException
from jose import jwt

from app.config import get_settings
from app.models import User
from app.security import (
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


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.user_id = uuid.uuid4()
        self.user = User(
            id=self.user_id,
            email="test@example.com",
            role="patient",
            is_active=True,
        )

    def test_get_current_user_valid_token(self):
        token = create_access_token(self.user_id, role="patient")
        self.db.get.return_value = self.user

        current_user = get_current_user(token=token, db=self.db)
        self.assertEqual(current_user, self.user)
        self.db.get.assert_called_once_with(User, self.user_id)

    def test_get_current_user_invalid_jwt_token_raises_401(self):
        invalid_token = "invalid.jwt.token"
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=invalid_token, db=self.db)

        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(ctx.exception.detail, "Could not validate credentials")
        self.assertEqual(ctx.exception.headers, {"WWW-Authenticate": "Bearer"})

    def test_get_current_user_tampered_jwt_signature_raises_401(self):
        token = create_access_token(self.user_id, role="patient")
        tampered_token = token[:-5] + "XXXXX"
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=tampered_token, db=self.db)

        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_current_user_missing_sub_claim_raises_401(self):
        payload = {"role": "patient"}
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=token, db=self.db)

        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_current_user_nonexistent_user_raises_401(self):
        token = create_access_token(self.user_id, role="patient")
        self.db.get.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=token, db=self.db)

        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_current_user_inactive_user_raises_401(self):
        token = create_access_token(self.user_id, role="patient")
        self.user.is_active = False
        self.db.get.return_value = self.user

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=token, db=self.db)

        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auth_version_invalidates_pre_rotation_session(self):
        token = create_access_token(self.user_id, role="patient", auth_version=1)
        self.user.auth_version = 2
        self.db.get.return_value = self.user

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=token, db=self.db)

        self.assertEqual(ctx.exception.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_require_roles_success(self):
        dep = require_roles("patient", "admin_clinical")
        res = dep(user=self.user)
        self.assertEqual(res, self.user)

    def test_require_roles_forbidden(self):
        dep = require_roles("therapist")
        with self.assertRaises(HTTPException) as ctx:
            dep(user=self.user)

        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ctx.exception.detail, "Insufficient permissions")

    def test_require_role_helpers(self):
        self.user.role = "patient"
        self.assertEqual(require_patient(user=self.user), self.user)

        self.user.role = "therapist"
        self.assertEqual(require_professional(user=self.user), self.user)

        self.user.role = "admin_clinical"
        self.assertEqual(require_admin(user=self.user), self.user)

    def test_password_hashing_and_verification(self):
        plain = "SuperSecretPassword123!"
        hashed = hash_password(plain)

        self.assertNotEqual(plain, hashed)
        self.assertTrue(verify_password(plain, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_verify_password_invalid_hash_value_error(self):
        self.assertFalse(verify_password("password", "invalid_hash_string"))
    def test_hash_and_verify_password(self):
        pw = "SuperSecret123"
        hashed = hash_password(pw)
        self.assertTrue(verify_password(pw, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_verify_password_invalid_hash_returns_false(self):
        self.assertFalse(verify_password("password", "invalid_hash_format"))

    def test_verify_password_invalid_hash_variants_return_false(self):
        invalid_hashes = ("", "not_a_bcrypt_hash", "1234567890" * 3)
        for invalid_hash in invalid_hashes:
            with self.subTest(invalid_hash=invalid_hash):
                self.assertFalse(verify_password("SecretPassword123", invalid_hash))

    def test_new_passwords_reject_bcrypt_truncation_lengths(self):
        # New credentials must never silently collapse to the first 72 bytes.
        with self.assertRaises(ValueError):
            hash_password("A" * 73)

    def test_get_current_user_valid_token(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id, "patient")

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.is_active = True
        mock_user.role = "patient"

        mock_db = MagicMock()
        mock_db.get.return_value = mock_user

        user = get_current_user(token=token, db=mock_db)
        self.assertEqual(user, mock_user)
        mock_db.get.assert_called_once_with(User, user_id)

    def test_get_current_user_jwt_error_malformed_token(self):
        mock_db = MagicMock()
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token="not.a.valid.jwt.token", db=mock_db)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Could not validate credentials")
        mock_db.get.assert_not_called()

    def test_get_current_user_jwt_error_invalid_signature(self):
        user_id = uuid.uuid4()
        token = jwt.encode({"sub": str(user_id)}, "wrong_secret", algorithm=settings.jwt_algorithm)
        mock_db = MagicMock()

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=token, db=mock_db)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Could not validate credentials")
        mock_db.get.assert_not_called()

    def test_get_current_user_missing_sub_claim(self):
        token = jwt.encode({"role": "patient"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        mock_db = MagicMock()

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=token, db=mock_db)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Could not validate credentials")
        mock_db.get.assert_not_called()

    def test_get_current_user_not_found_or_inactive(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id, "patient")

        # Case 1: User not found in DB
        mock_db = MagicMock()
        mock_db.get.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=token, db=mock_db)
        self.assertEqual(ctx.exception.status_code, 401)

        # Case 2: User found but inactive
        mock_user = MagicMock(spec=User)
        mock_user.is_active = False
        mock_db.get.return_value = mock_user

        with self.assertRaises(HTTPException) as ctx:
            get_current_user(token=token, db=mock_db)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_require_roles_permission(self):
        user_patient = MagicMock(spec=User, role="patient")
        user_therapist = MagicMock(spec=User, role="therapist")

        dep = require_roles("therapist", "admin_clinical")

        # Allowed role
        self.assertEqual(dep(user=user_therapist), user_therapist)

        # Denied role raises 403
        with self.assertRaises(HTTPException) as ctx:
            dep(user=user_patient)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "Insufficient permissions")


if __name__ == "__main__":
    unittest.main()

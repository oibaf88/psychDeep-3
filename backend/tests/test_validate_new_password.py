import unittest
from app.security import validate_new_password, _PASSWORD_MIN_LENGTH, _BCRYPT_MAX_BYTES

class TestValidateNewPassword(unittest.TestCase):
    def test_valid_password(self):
        # A password that meets length requirements and is under bcrypt max bytes
        valid_password = "a" * _PASSWORD_MIN_LENGTH
        validate_new_password(valid_password)  # Should not raise an exception

    def test_password_too_short(self):
        # A password shorter than the minimum length
        short_password = "a" * (_PASSWORD_MIN_LENGTH - 1)
        with self.assertRaises(ValueError) as context:
            validate_new_password(short_password)
        self.assertIn(f"La contraseña debe tener al menos {_PASSWORD_MIN_LENGTH} caracteres.", str(context.exception))

    def test_password_not_string(self):
        # A password that is not a string
        invalid_password = 1234567890123
        with self.assertRaises(ValueError) as context:
            validate_new_password(invalid_password)
        self.assertIn(f"La contraseña debe tener al menos {_PASSWORD_MIN_LENGTH} caracteres.", str(context.exception))

    def test_password_too_long_for_bcrypt(self):
        # A password that exceeds the bcrypt max bytes when encoded
        long_password = "a" * (_BCRYPT_MAX_BYTES + 1)
        with self.assertRaises(ValueError) as context:
            validate_new_password(long_password)
        self.assertIn("La contraseña supera el límite seguro de 72 bytes de bcrypt.", str(context.exception))

    def test_password_multibyte_characters_exceeding_bcrypt(self):
        # A password that is within string length but exceeds byte length due to multibyte characters
        # 'ñ' is 2 bytes in UTF-8. 37 'ñ's = 74 bytes.
        multibyte_password = "ñ" * 37
        self.assertTrue(len(multibyte_password) >= _PASSWORD_MIN_LENGTH)
        self.assertTrue(len(multibyte_password.encode('utf-8')) > _BCRYPT_MAX_BYTES)

        with self.assertRaises(ValueError) as context:
            validate_new_password(multibyte_password)
        self.assertIn("La contraseña supera el límite seguro de 72 bytes de bcrypt.", str(context.exception))

if __name__ == '__main__':
    unittest.main()

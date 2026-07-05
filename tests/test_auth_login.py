import unittest
from auth import verify_password, hash_password


class AuthLoginTests(unittest.TestCase):
    def test_verify_password_supports_plaintext_legacy_hashes(self):
        self.assertTrue(verify_password('welcome123', 'welcome123'))

    def test_verify_password_supports_bcrypt_hashes(self):
        hashed = hash_password('welcome123')
        self.assertTrue(verify_password('welcome123', hashed))


if __name__ == '__main__':
    unittest.main()

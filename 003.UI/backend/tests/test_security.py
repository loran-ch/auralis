from datetime import datetime, timedelta, timezone
import re
import unittest

from jose import jwt

from config import CORS_ORIGIN_REGEX, JWT_ALGORITHM, JWT_SECRET
from routers.auth import _detect_image_extension
from routers.lecture import _detect_audio_extension
from schemas.auth import LoginReq
from utils.security import (
    create_token_pair,
    decode_token,
    get_refresh_user_id,
    get_user_id_from_token,
    hash_password,
    hash_token,
    verify_password,
)


class PasswordSecurityTests(unittest.TestCase):
    def test_password_round_trip(self):
        hashed = hash_password("123456")
        self.assertTrue(verify_password("123456", hashed))
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_malformed_password_hash_is_rejected(self):
        self.assertFalse(verify_password("123456", "not-a-bcrypt-hash"))

    def test_login_schema_normalizes_mainland_phone(self):
        request = LoginReq(account="13800000002", password="123456")
        self.assertEqual(request.account, "+8613800000002")


class TokenSecurityTests(unittest.TestCase):
    def test_access_and_refresh_tokens_have_separate_types(self):
        tokens = create_token_pair(42)
        self.assertEqual(get_user_id_from_token(tokens["access_token"]), 42)
        self.assertEqual(get_refresh_user_id(tokens["refresh_token"]), 42)
        self.assertIsNone(get_user_id_from_token(tokens["refresh_token"]))
        self.assertIsNone(get_refresh_user_id(tokens["access_token"]))

    def test_token_pairs_are_unique(self):
        first = create_token_pair(42)
        second = create_token_pair(42)
        self.assertNotEqual(first["access_token"], second["access_token"])
        self.assertNotEqual(first["refresh_token"], second["refresh_token"])

    def test_expired_and_invalid_subject_tokens_are_rejected(self):
        expired = jwt.encode(
            {
                "sub": "42",
                "type": "access",
                "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        invalid_subject = jwt.encode(
            {
                "sub": "not-an-id",
                "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=1),
            },
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
        self.assertIsNone(decode_token(expired))
        self.assertIsNone(get_user_id_from_token(invalid_subject))

    def test_database_token_value_is_a_digest(self):
        token = create_token_pair(42)["access_token"]
        digest = hash_token(token)
        self.assertNotEqual(token, digest)
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, hash_token(token))


class ImageUploadSecurityTests(unittest.TestCase):
    def test_image_format_uses_file_signature(self):
        self.assertEqual(_detect_image_extension(b"\xff\xd8\xffrest"), ".jpg")
        self.assertEqual(_detect_image_extension(b"\x89PNG\r\n\x1a\nrest"), ".png")
        self.assertEqual(_detect_image_extension(b"GIF89arest"), ".gif")
        self.assertEqual(_detect_image_extension(b"RIFF1234WEBPrest"), ".webp")
        self.assertIsNone(_detect_image_extension(b"<script>alert(1)</script>"))

    def test_audio_format_uses_file_signature(self):
        self.assertEqual(_detect_audio_extension(b"\x1aE\xdf\xa3webm"), ".webm")
        self.assertEqual(_detect_audio_extension(b"OggSdata"), ".ogg")
        self.assertEqual(_detect_audio_extension(b"RIFF1234WAVEdata"), ".wav")
        self.assertEqual(_detect_audio_extension(b"0000ftypM4A"), ".m4a")
        self.assertIsNone(_detect_audio_extension(b"not audio"))


class DevelopmentCorsTests(unittest.TestCase):
    def test_private_network_h5_origins_are_allowed_in_development(self):
        if CORS_ORIGIN_REGEX is None:
            self.skipTest("生产环境不启用开发 CORS 规则")
        for origin in (
            "http://10.0.2.2:5173",
            "http://192.168.2.198:5173",
            "https://172.20.0.2:5173",
        ):
            self.assertIsNotNone(re.fullmatch(CORS_ORIGIN_REGEX, origin), origin)

    def test_public_origins_are_not_implicitly_allowed(self):
        if CORS_ORIGIN_REGEX is None:
            self.skipTest("生产环境不启用开发 CORS 规则")
        self.assertIsNone(re.fullmatch(CORS_ORIGIN_REGEX, "https://example.com"))


if __name__ == "__main__":
    unittest.main()

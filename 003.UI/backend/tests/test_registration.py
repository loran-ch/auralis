import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from routers import auth as auth_router
from schemas.auth import RegisterReq
from services.captcha import (create_registration_captcha,
                              verify_registration_captcha)
from services.registration import (get_registration_setting,
                                   update_registration_setting)


class RegistrationSchemaTests(unittest.TestCase):
    def test_registration_requires_matching_passwords(self):
        with self.assertRaises(ValidationError):
            RegisterReq(
                username="student_01",
                password="secret12",
                confirm_password="different12",
                captcha_token="x" * 20,
                captcha_code="ABCD",
            )

    def test_phone_is_optional_for_account_registration(self):
        request = RegisterReq(
            username="student_01",
            password="secret12",
            confirm_password="secret12",
            captcha_token="x" * 20,
            captcha_code="ABCD",
        )
        self.assertIsNone(request.phone)


class CaptchaTests(unittest.TestCase):
    def test_captcha_is_embedded_and_verifiable(self):
        db = FakeCaptchaDb()
        with patch("services.captcha.secrets.choice", side_effect=list("ABCD")):
            result = create_registration_captcha(db)
        self.assertTrue(result["image"].startswith("data:image/svg+xml;base64,"))
        self.assertGreater(len(result["captcha_token"]), 20)
        self.assertTrue(
            verify_registration_captcha(db, result["captcha_token"], "abcd")
        )
        self.assertFalse(
            verify_registration_captcha(db, result["captcha_token"], "ABCD")
        )

    def test_wrong_answer_also_consumes_captcha(self):
        db = FakeCaptchaDb()
        with patch("services.captcha.secrets.choice", side_effect=list("ABCD")):
            result = create_registration_captcha(db)
        self.assertFalse(
            verify_registration_captcha(db, result["captcha_token"], "WXYZ")
        )
        self.assertFalse(
            verify_registration_captcha(db, result["captcha_token"], "ABCD")
        )


class FakeCaptchaQuery:
    def __init__(self, db):
        self.db = db

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.db.latest if self.db.latest and not self.db.latest.used else None


class FakeCaptchaDb:
    def __init__(self):
        self.latest = None

    def add(self, item):
        self.latest = item

    def commit(self):
        return None

    def query(self, _model):
        return FakeCaptchaQuery(self)


class FakeAuditQuery:
    def __init__(self, latest):
        self.latest = latest

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.latest


class FakeRegistrationDb:
    def __init__(self, latest=None):
        self.latest = latest
        self.added = None

    def query(self, _model):
        return FakeAuditQuery(self.latest)

    def add(self, entry):
        self.added = entry
        self.latest = entry

    def commit(self):
        if self.added:
            self.added.id = 1

    def refresh(self, _entry):
        return None


class RegistrationSettingTests(unittest.TestCase):
    def test_registration_is_open_by_default(self):
        self.assertTrue(get_registration_setting(FakeRegistrationDb())["enabled"])

    def test_super_admin_can_pause_registration(self):
        db = FakeRegistrationDb()
        admin = SimpleNamespace(id=9, nickname="超级管理员", username="root")
        result = update_registration_setting(db, False, admin, "127.0.0.1")
        self.assertFalse(result["enabled"])
        self.assertEqual(db.added.detail["previous_enabled"], True)
        self.assertEqual(db.added.action, "system.registration.update")


class RegistrationGuardTests(unittest.TestCase):
    def test_paused_registration_blocks_captcha_before_generation(self):
        with (
            patch.object(auth_router, "registration_is_enabled", return_value=False),
            patch.object(auth_router, "create_registration_captcha") as create,
        ):
            with self.assertRaises(HTTPException) as raised:
                auth_router.api_registration_captcha(db=object())
        self.assertEqual(raised.exception.status_code, 403)
        create.assert_not_called()

    def test_paused_registration_blocks_submit_before_account_creation(self):
        request = RegisterReq(
            username="student_02",
            password="secret12",
            confirm_password="secret12",
            captcha_token="x" * 20,
            captcha_code="ABCD",
        )
        with (
            patch.object(auth_router, "registration_is_enabled", return_value=False),
            patch.object(auth_router, "register") as create_user,
        ):
            with self.assertRaises(HTTPException) as raised:
                auth_router.api_register(request, None, object())
        self.assertEqual(raised.exception.status_code, 403)
        create_user.assert_not_called()


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

from pydantic import ValidationError

from schemas.assistant import AssistantAskThreadReq
from services.assistant_images import (compose_question_with_screenshot,
                                       is_owned_assistant_image)
from services.image_ocr import detect_image_extension, ocr_image_path


class ImageOcrHelperTests(unittest.TestCase):
    def test_detect_image_extension(self):
        self.assertEqual(detect_image_extension(b"\xff\xd8\xff\xe0rest"), ".jpg")
        self.assertEqual(detect_image_extension(b"\x89PNG\r\n\x1a\n...."), ".png")
        self.assertIsNone(detect_image_extension(b"hello"))

    def test_ocr_missing_file(self):
        result = ocr_image_path(Path("does-not-exist-xyz.png"))
        self.assertEqual(result["ocr_status"], "failed")


class AssistantImageComposeTests(unittest.TestCase):
    def test_compose_with_ocr(self):
        display, enriched = compose_question_with_screenshot("这是什么错？", "NullPointerException at line 12")
        self.assertEqual(display, "这是什么错？")
        self.assertIn("NullPointerException", enriched)
        self.assertIn("【截图文字识别】", enriched)

    def test_compose_image_only_uses_default(self):
        display, enriched = compose_question_with_screenshot("", "TypeError: x is not defined")
        self.assertTrue(display)
        self.assertIn("TypeError", enriched)

    def test_owned_image_url(self):
        self.assertTrue(is_owned_assistant_image("/uploads/assistant/9_1_abc.jpg", 9))
        self.assertFalse(is_owned_assistant_image("/uploads/assistant/8_1_abc.jpg", 9))
        self.assertFalse(is_owned_assistant_image("/uploads/attachments/x.png", 9))


class AskSchemaScreenshotTests(unittest.TestCase):
    def test_requires_question_or_image(self):
        with self.assertRaises(ValidationError):
            AssistantAskThreadReq(question="")

    def test_image_only_ok(self):
        req = AssistantAskThreadReq(
            question="",
            image_url="/uploads/assistant/1_2_abcd.png",
            image_ocr="error code 500",
        )
        self.assertEqual(req.image_ocr, "error code 500")

    def test_rejects_foreign_upload_prefix(self):
        with self.assertRaises(ValidationError):
            AssistantAskThreadReq(
                question="看看",
                image_url="/uploads/attachments/x.png",
            )


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock, patch

from services.attachments import extension_for_upload
from services.briefing import supplement_briefing_item


class AttachmentExtensionTests(unittest.TestCase):
    def test_detects_common_types(self):
        self.assertEqual(extension_for_upload("image/png", b"\x89PNG\r\n\x1a\n...."), ".png")
        self.assertEqual(extension_for_upload("application/pdf", b"%PDF-1.4"), ".pdf")
        self.assertEqual(extension_for_upload("image/jpeg", b"\xff\xd8\xff\xe0"), ".jpg")
        self.assertEqual(
            extension_for_upload(
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                b"PK....",
                "a.pptx",
            ),
            ".pptx",
        )
        self.assertIsNone(extension_for_upload("text/plain", b"hello"))


class BriefingSupplementTests(unittest.TestCase):
    def test_append_user_assignment(self):
        row = MagicMock()
        row.status = "ready"
        row.overview = ""
        row.outline = []
        row.key_points = []
        row.exam_hints = []
        row.questions = []
        row.terms = []
        row.assignments = []
        row.provider = "extractive"
        row.source_sentence_count = 0
        row.edit_status = "auto"
        row.generated_at = None
        row.edited_at = None
        row.previous_payload = None
        db = MagicMock()
        with patch("services.briefing.get_briefing", return_value=row), \
             patch("services.briefing._sentence_lookup", return_value={}), \
             patch("services.briefing.ensure_briefing_table"):
            result = supplement_briefing_item(
                db, 1, 2,
                section="assignments",
                text="完成第3章习题",
                sentence_order=0,
                needs_confirmation=False,
                source="user_added",
            )
        self.assertEqual(len(result.assignments), 1)
        self.assertEqual(result.assignments[0]["source"], "user_added")
        self.assertEqual(result.edit_status, "edited")
        self.assertFalse(result.assignments[0]["needs_confirmation"])


if __name__ == "__main__":
    unittest.main()

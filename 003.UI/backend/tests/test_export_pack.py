import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.attachments import (ATTACHMENT_CATEGORIES, extension_for_upload,
                                  max_upload_mb_for)
from services.export_pack import (briefing_to_markdown, build_materials_zip,
                                  content_disposition)


class AttachmentTypeTests(unittest.TestCase):
    def test_material_category_supported(self):
        self.assertIn("material", ATTACHMENT_CATEGORIES)

    def test_detects_ppt_types(self):
        self.assertEqual(
            extension_for_upload(
                "application/vnd.ms-powerpoint",
                b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1....",
                "deck.ppt",
            ),
            ".ppt",
        )
        self.assertEqual(
            extension_for_upload(
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                b"PK\x03\x04........",
                "deck.pptx",
            ),
            ".pptx",
        )
        self.assertEqual(
            extension_for_upload("application/octet-stream", b"PK\x03\x04....", "slides.pptx"),
            ".pptx",
        )

    def test_material_size_limit(self):
        self.assertGreaterEqual(max_upload_mb_for("material", "application/pdf", ".pdf"), 10)
        self.assertEqual(max_upload_mb_for("assignment", "image/png", ".png"), 10)


class BriefingExportTests(unittest.TestCase):
    def test_markdown_contains_sections(self):
        lecture = SimpleNamespace(
            id=12,
            title="热力学第1讲",
            course_name="物理",
            session_number=1,
            lecture_date="2026-08-01",
            duration_seconds=3600,
            audio_url="/uploads/audio/a.webm",
        )
        briefing = {
            "status": "ready",
            "overview": "本节讨论熵。",
            "outline": [{"title": "开场", "start_order": 1}],
            "key_points": [{"text": "熵不减", "sentence_order": 4}],
            "exam_hints": [],
            "assignments": [{"text": "完成习题", "sentence_order": 9}],
            "questions": [],
            "terms": [{"term": "Entropy", "explanation": "熵"}],
        }
        markdown = briefing_to_markdown(lecture, briefing)
        self.assertIn("# 热力学第1讲", markdown)
        self.assertIn("本节讨论熵", markdown)
        self.assertIn("熵不减", markdown)
        self.assertIn("完成习题", markdown)
        self.assertIn("Entropy", markdown)

    def test_content_disposition_has_filename(self):
        header = content_disposition("课堂-简报.md")
        self.assertIn("attachment;", header)
        self.assertIn("filename*=UTF-8''", header)

    def test_materials_zip_contains_briefing(self):
        lecture = SimpleNamespace(
            id=12,
            title="热力学",
            course_name="物理",
            session_number=1,
            lecture_date=None,
            duration_seconds=0,
            audio_url=None,
        )
        db = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "note.pdf"
            file_path.write_bytes(b"%PDF-1.4 demo")
            attachment = SimpleNamespace(
                id=1,
                title="讲义",
                url="/uploads/attachments/note.pdf",
            )
            with patch("services.export_pack.build_briefing_markdown", return_value="# hi\n"), \
                 patch("services.export_pack.list_attachments", return_value=[attachment]), \
                 patch("services.export_pack.local_attachment_path", return_value=file_path):
                payload = build_materials_zip(db, lecture, 1)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            self.assertIn("briefing.md", names)
            self.assertIn("README.md", names)
            self.assertTrue(any(name.startswith("attachments/") for name in names))


if __name__ == "__main__":
    unittest.main()

import unittest

from services.guide import (
    DEFAULT_GUIDES,
    RECORDER_FEATURES_SLUG,
    default_guide,
    sanitize_icon,
    sanitize_items,
)


class GuideSanitizeTests(unittest.TestCase):
    def test_invalid_icon_falls_back_to_info(self):
        self.assertEqual(sanitize_icon("subtitles"), "subtitles")
        self.assertEqual(sanitize_icon("javascript:alert(1)"), "info")
        self.assertEqual(sanitize_icon("<script>"), "info")
        self.assertEqual(sanitize_icon(""), "info")

    def test_sanitize_items_drops_empty_and_caps_length(self):
        items = sanitize_items([
            {"icon": "star", "title": "收藏", "body": "把句子标成重点"},
            {"icon": "bad icon", "title": "  ", "body": "无标题"},
            {"title": "只有标题"},
            "not-a-dict",
        ] + [{"icon": "info", "title": "x", "body": "y"}] * 10)
        self.assertEqual(len(items), 8)
        self.assertEqual(items[0]["icon"], "star")
        self.assertEqual(items[1]["icon"], "info")

    def test_default_guide_has_five_recorder_items(self):
        guide = default_guide(RECORDER_FEATURES_SLUG)
        self.assertEqual(guide["slug"], RECORDER_FEATURES_SLUG)
        self.assertEqual(len(guide["items"]), 5)
        self.assertIn("实时双语字幕", [item["title"] for item in guide["items"]])

    def test_unknown_slug_uses_recorder_defaults(self):
        guide = default_guide("unknown")
        self.assertEqual(guide["items"], DEFAULT_GUIDES[RECORDER_FEATURES_SLUG]["items"])


if __name__ == "__main__":
    unittest.main()

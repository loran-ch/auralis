import unittest
from unittest.mock import MagicMock, patch

from services.briefing import (
    build_extractive_briefing,
    merge_llm_briefing,
    _normalize_assignments,
    _normalize_citation_items,
    patch_briefing,
    confirm_briefing_assignment,
    delete_briefing_assignment,
)


def _sent(order, source, translated, tag=None, start=0):
    return {
        "id": order,
        "sentence_order": order,
        "source_text": source,
        "translated_text": translated,
        "start_offset_ms": start,
        "tag": tag,
    }


class ExtractiveBriefingTests(unittest.TestCase):
    def setUp(self):
        self.sentences = [
            _sent(1, "Today we discuss thermodynamics.", "今天我们讨论热力学。", start=0),
            _sent(2, "Energy cannot be created or destroyed.", "能量不能被创造或毁灭。", start=8000),
            _sent(3, "This will definitely be on the exam.", "这肯定会在考试中出现。", "exam", 16000),
            _sent(4, "Entropy is defined as the measure of disorder.", "熵定义为无序程度的度量。", "definition", 24000),
            _sent(5, "Why does the entropy of an isolated system never decrease?", "为什么孤立系统的熵永不减少？", "question", 32000),
            _sent(6, "Please remember this formula, it is important.", "请记住这个公式，它很重要。", start=40000),
            _sent(7, "A piston in a cylinder is a simple example.", "气缸中的活塞是一个简单例子。", start=48000),
            _sent(8, "We now move to the second law.", "现在我们进入第二定律。", start=56000),
            _sent(9, "Homework is due on Friday.", "作业周五截止。", start=64000),
        ]

    def test_overview_contains_course_and_outline(self):
        briefing = build_extractive_briefing("热力学", 540, self.sentences, "zh-CN")
        self.assertEqual(briefing["provider"], "extractive")
        self.assertIn("热力学", briefing["overview"])
        self.assertIn("9 句", briefing["overview"])
        self.assertGreaterEqual(len(briefing["outline"]), 1)
        self.assertEqual(briefing["outline"][0]["start_order"], 1)

    def test_exam_and_question_bookmarks_are_classified(self):
        briefing = build_extractive_briefing("热力学", 540, self.sentences, "zh-CN")
        exam_orders = {item["sentence_order"] for item in briefing["exam_hints"]}
        question_orders = {item["sentence_order"] for item in briefing["questions"]}
        self.assertIn(3, exam_orders)
        self.assertIn(9, exam_orders)
        self.assertIn(5, question_orders)

    def test_definition_pattern_becomes_term(self):
        briefing = build_extractive_briefing("热力学", 60, self.sentences, "zh-CN")
        terms = {item["term"].lower() for item in briefing["terms"]}
        self.assertTrue(any("entropy" in term for term in terms))

    def test_assignment_is_cited_and_requires_confirmation(self):
        briefing = build_extractive_briefing("热力学", 60, self.sentences, "zh-CN")
        assignment = next(item for item in briefing["assignments"] if item["sentence_order"] == 9)
        self.assertIn("作业", assignment["text"])
        self.assertTrue(assignment["needs_confirmation"])
        self.assertIsNone(assignment["due_date"])

    def test_empty_sentences(self):
        briefing = build_extractive_briefing("空课", 0, [], "zh-CN")
        self.assertEqual(briefing["outline"], [])
        self.assertEqual(briefing["key_points"], [])


class MergeLlmBriefingTests(unittest.TestCase):
    def test_invalid_sentence_order_is_dropped(self):
        sentences = [_sent(1, "Hello", "你好")]
        extractive = build_extractive_briefing("课", 60, sentences, "zh-CN")
        merged = merge_llm_briefing(
            extractive,
            {
                "overview": "模型概述",
                "key_points": [{"text": "幻觉", "sentence_order": 99}],
                "outline": [],
            },
            sentences,
        )
        self.assertEqual(merged["overview"], "模型概述")
        self.assertEqual(merged["key_points"], extractive["key_points"])

    def test_llm_assignment_requires_real_citation(self):
        sentences = [_sent(1, "Homework is due on Friday.", "作业周五截止。")]
        extractive = build_extractive_briefing("课", 60, sentences, "zh-CN")
        merged = merge_llm_briefing(
            extractive,
            {"assignments": [{"text": "完成作业", "sentence_order": 1}]},
            sentences,
        )
        self.assertEqual(merged["assignments"][0]["sentence_order"], 1)
        self.assertTrue(merged["assignments"][0]["needs_confirmation"])


class BriefingEditNormalizeTests(unittest.TestCase):
    def test_invalid_citation_order_rejected(self):
        lookup = {1: _sent(1, "A", "甲", start=100)}
        with self.assertRaises(ValueError):
            _normalize_citation_items(
                [{"text": "错引用", "sentence_order": 9}],
                lookup,
                field="key_points",
            )

    def test_zero_order_means_uncited_supplement(self):
        lookup = {1: _sent(1, "A", "甲", start=100)}
        items = _normalize_citation_items(
            [{"text": "补充要点", "sentence_order": 0}],
            lookup,
            field="key_points",
        )
        self.assertEqual(items[0]["sentence_order"], 0)
        self.assertEqual(items[0]["text"], "补充要点")

    def test_assignment_confirm_flag_preserved(self):
        lookup = {9: _sent(9, "Homework", "作业", start=64000)}
        items = _normalize_assignments(
            [{"text": "周五交作业", "sentence_order": 9, "needs_confirmation": False}],
            lookup,
        )
        self.assertFalse(items[0]["needs_confirmation"])
        self.assertEqual(items[0]["start_offset_ms"], 64000)


class BriefingPatchServiceTests(unittest.TestCase):
    def _row(self):
        row = MagicMock()
        row.status = "ready"
        row.overview = "旧概述"
        row.outline = []
        row.key_points = [{"text": "旧要点", "sentence_order": 1, "start_offset_ms": 0}]
        row.exam_hints = []
        row.questions = []
        row.terms = []
        row.assignments = [{
            "text": "作业", "sentence_order": 1, "start_offset_ms": 0,
            "needs_confirmation": True, "source_text": "", "due_date": None,
        }]
        row.provider = "extractive"
        row.source_sentence_count = 1
        row.edit_status = "auto"
        row.generated_at = None
        row.edited_at = None
        row.previous_payload = None
        return row

    def test_patch_marks_edited_and_keeps_previous(self):
        row = self._row()
        db = MagicMock()
        with patch("services.briefing.get_briefing", return_value=row), \
             patch("services.briefing._sentence_lookup", return_value={1: _sent(1, "A", "甲", start=12)}), \
             patch("services.briefing.ensure_briefing_table"):
            result = patch_briefing(db, 1, 2, {
                "overview": "新概述",
                "key_points": [{"text": "新要点", "sentence_order": 1}],
            })
        self.assertEqual(result.overview, "新概述")
        self.assertEqual(result.edit_status, "edited")
        self.assertIsNotNone(result.previous_payload)
        self.assertEqual(result.previous_payload["overview"], "旧概述")
        db.commit.assert_called()

    def test_confirm_and_delete_assignment(self):
        row = self._row()
        db = MagicMock()
        with patch("services.briefing.get_briefing", return_value=row), \
             patch("services.briefing.ensure_briefing_table"):
            confirm_briefing_assignment(db, 1, 2, 0)
            self.assertFalse(row.assignments[0]["needs_confirmation"])
            delete_briefing_assignment(db, 1, 2, 0)
            self.assertEqual(row.assignments, [])


if __name__ == "__main__":
    unittest.main()

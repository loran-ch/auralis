import unittest

from services.briefing import build_extractive_briefing, merge_llm_briefing


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


if __name__ == "__main__":
    unittest.main()

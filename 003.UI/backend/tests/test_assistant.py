import unittest

from services.assistant import (build_template_answer, classify_question,
                                merge_llm_answer, retrieve_sentences)


def _sent(order, source, translated, tag=None):
    return {
        "sentence_order": order,
        "source_text": source,
        "translated_text": translated,
        "start_offset_ms": order * 8000,
        "tag": tag,
    }


SENTENCES = [
    _sent(1, "Today we discuss thermodynamics.", "今天我们讨论热力学。"),
    _sent(3, "This will be on the exam.", "这会在考试中出现。", "exam"),
    _sent(4, "Entropy is defined as disorder.", "熵定义为无序。", "definition"),
    _sent(5, "Why does entropy never decrease?", "为什么熵永不减少？", "question"),
]


class ClassifyQuestionTests(unittest.TestCase):
    def test_four_preset_intents(self):
        self.assertEqual(classify_question("这节课讲了什么"), "overview")
        self.assertEqual(classify_question("教授强调了哪些考点"), "exam")
        self.assertEqual(classify_question("这个概念他原话怎么说"), "quote")
        self.assertEqual(classify_question("我标了疑问的几句帮我解释"), "bookmarked_questions")


class RetrieveAndTemplateTests(unittest.TestCase):
    def test_overview_uses_outline_start_orders(self):
        briefing = {"overview": "本节讨论热力学。", "outline": [{"title": "开场", "start_order": 1}]}
        intent, hits = retrieve_sentences("这节课讲了什么", SENTENCES, briefing)
        self.assertEqual(intent, "overview")
        self.assertEqual(hits[0]["sentence_order"], 1)
        answer = build_template_answer("这节课讲了什么", intent, hits, briefing)
        self.assertIn("热力学", answer["answer"])
        self.assertIn("#1", answer["answer"])

    def test_exam_only_returns_exam_evidence(self):
        intent, hits = retrieve_sentences("教授强调了哪些考点", SENTENCES, {})
        self.assertEqual(intent, "exam")
        self.assertEqual([item["sentence_order"] for item in hits], [3])
        answer = build_template_answer("考点", intent, hits, {})
        self.assertIn("#3", answer["answer"])

    def test_quote_puts_source_text_first(self):
        intent, hits = retrieve_sentences("entropy 他原话怎么说", SENTENCES, {})
        self.assertEqual(intent, "quote")
        self.assertTrue(any(item["sentence_order"] == 4 for item in hits))
        answer = build_template_answer("原话", intent, hits, {})
        self.assertIn("原文", answer["answer"])
        self.assertIn("Entropy is defined", answer["answer"])

    def test_bookmarked_questions_without_tags(self):
        intent, hits = retrieve_sentences("解释我的疑问", SENTENCES[:3], {})
        self.assertEqual(intent, "bookmarked_questions")
        self.assertEqual(hits, [])
        answer = build_template_answer("疑问", intent, hits, {})
        self.assertIn("疑问", answer["answer"])
        self.assertEqual(answer["citations"], [])

    def test_unknown_topic_does_not_invent(self):
        intent, hits = retrieve_sentences("量子纠缠是什么", SENTENCES, {})
        self.assertEqual(intent, "search")
        self.assertEqual(hits, [])
        answer = build_template_answer("量子纠缠是什么", intent, hits, {})
        self.assertIn("没有提到", answer["answer"])


class MergeLlmAnswerTests(unittest.TestCase):
    def test_invalid_citation_falls_back_to_template(self):
        template = {
            "answer": "模板 #3",
            "citations": [{"sentence_order": 3}],
            "provider": "extractive",
        }
        merged = merge_llm_answer(
            template,
            {"answer": "幻觉内容", "citation_orders": [99]},
            SENTENCES,
        )
        self.assertEqual(merged, template)

    def test_valid_orders_are_kept(self):
        template = {"answer": "模板", "citations": [], "provider": "extractive"}
        merged = merge_llm_answer(
            template,
            {"answer": "考点在 #3", "citation_orders": [3, 3, "x"]},
            SENTENCES,
        )
        self.assertEqual(merged["answer"], "考点在 #3")
        self.assertEqual([item["sentence_order"] for item in merged["citations"]], [3])


if __name__ == "__main__":
    unittest.main()

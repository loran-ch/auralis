import unittest
from unittest.mock import MagicMock, patch

from services.assistant import (build_template_answer, classify_question,
                                merge_llm_answer, retrieve_sentences,
                                _merge_scope_stream_answer,
                                _stream_scope_assistant_llm)


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
        self.assertIn("没有直接匹配", answer["answer"])

    def test_chinese_keyword_can_match_inside_sentence(self):
        intent, hits = retrieve_sentences("热力学是什么意思", SENTENCES, {})
        self.assertEqual(intent, "search")
        self.assertTrue(any(item["sentence_order"] == 1 for item in hits))


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


class StreamAssistantTests(unittest.TestCase):
    def test_stream_answer_only_keeps_retrieved_citations(self):
        hits = [dict(SENTENCES[1], lecture_id=12, lecture_title="热力学", session_number=1)]
        template = {"answer": "模板回答", "citations": [], "provider": "extractive"}
        merged = _merge_scope_stream_answer(
            template,
            "考试内容见 [L12S3]，不要相信 [L99S3]。",
            hits,
        )
        self.assertIn("L12S3", merged["answer"])
        self.assertEqual([item["lecture_id"] for item in merged["citations"]], [12])
        self.assertEqual([item["sentence_order"] for item in merged["citations"]], [3])

    def test_stream_answer_without_valid_citation_keeps_text(self):
        hits = [dict(SENTENCES[1], lecture_id=12)]
        template = {"answer": "模板回答", "citations": [], "provider": "extractive"}
        merged = _merge_scope_stream_answer(template, "没有引用的回答。", hits)
        self.assertEqual(merged["answer"], "没有引用的回答。")
        self.assertEqual([item["sentence_order"] for item in merged["citations"]], [3])

    def test_stream_answer_keeps_labeled_supplement_without_hits(self):
        template = {"answer": "模板回答", "citations": [], "provider": "extractive"}
        merged = _merge_scope_stream_answer(
            template,
            "课堂记录未直接提到。\n【补充说明】以下不是课堂原文：这是背景解释。【/补充说明】",
            [],
        )
        self.assertIn("【补充说明】", merged["answer"])
        self.assertEqual(merged["citations"], [])

    def test_openai_sse_deltas_are_yielded(self):
        class FakeResponse:
            ok = True

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def iter_lines(self, decode_unicode=False):
                return iter([
                    b'data: {"choices":[{"delta":{"content":"\xe7\xac\xac\xe4\xb8\x80\xe6\xae\xb5"}}]}',
                    'data: {"choices":[{"delta":{"content":"第二段 [L12S3]"}}]}'.encode("utf-8"),
                    b'data: [DONE]',
                ])

        hit = dict(SENTENCES[1], lecture_id=12, lecture_title="热力学", session_number=1)
        with patch("services.assistant.requests.post", return_value=FakeResponse()) as post:
            chunks = list(_stream_scope_assistant_llm("考点是什么", "热力学", "", [hit], []))
        self.assertEqual(chunks, ["第一段", "第二段 [L12S3]"])
        self.assertTrue(post.call_args.kwargs["stream"])
        self.assertTrue(post.call_args.kwargs["json"]["stream"])

    def test_extractive_path_emits_delta_then_done(self):
        from services.assistant import stream_scope_question

        class FakeLecture:
            id = 12
            title = "热力学"
            course_name = "物理"
            session_number = 1
            lecture_date = None
            started_at = None

        sentences = [dict(item) for item in SENTENCES]
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [FakeLecture()]
        with patch("services.assistant.BRIEFING_LLM_API_URL", ""), \
             patch("services.assistant.BRIEFING_LLM_API_KEY", ""), \
             patch("services.tools.agent.BRIEFING_LLM_API_URL", ""), \
             patch("services.tools.agent.BRIEFING_LLM_API_KEY", ""), \
             patch("services.tools.agent.load_sentence_rows", return_value=sentences), \
             patch("services.tools.notebook.load_sentence_rows", return_value=sentences), \
             patch("services.tools.notebook.get_briefing", return_value=None), \
             patch("services.tools.notebook.list_attachments", return_value=[]):
            events = list(stream_scope_question(
                db, [12], 1, "教授强调了哪些考点", scope_name="热力学",
            ))
        kinds = [event["type"] for event in events]
        self.assertIn("delta", kinds)
        self.assertIn("tool_start", kinds)
        self.assertEqual(kinds[-1], "done")
        self.assertTrue("".join(event.get("content", "") for event in events if event["type"] == "delta"))
        self.assertIn("#3", events[-1]["result"]["answer"])




if __name__ == "__main__":
    unittest.main()

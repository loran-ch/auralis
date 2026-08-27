import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.tools.notebook import (breakdown_assignment, list_assignments,
                                     make_assignment_id, parse_assignment_id,
                                     search_notebook, suggest_tools)
from services.tools.agent import _public_tool_result, _template_from_tools


class AssignmentIdTests(unittest.TestCase):
    def test_roundtrip(self):
        self.assertEqual(make_assignment_id(12, 0), "L12A0")
        self.assertEqual(parse_assignment_id("L12A0"), (12, 0))
        self.assertIsNone(parse_assignment_id("bad"))


class SuggestToolsTests(unittest.TestCase):
    def test_forced_hint(self):
        calls = suggest_tools("随便", hint="search_notebook")
        self.assertEqual(calls[0]["name"], "search_notebook")

    def test_assignment_id_forces_breakdown(self):
        calls = suggest_tools("帮我看看", assignment_id="L3A1")
        self.assertEqual(calls[0]["name"], "breakdown_assignment")
        self.assertEqual(calls[0]["arguments"]["assignment_id"], "L3A1")

    def test_homework_question(self):
        calls = suggest_tools("这门课有哪些作业")
        self.assertEqual(calls[0]["name"], "list_assignments")


class ToolExecutionTests(unittest.TestCase):
    def test_search_notebook_returns_hits(self):
        lecture = SimpleNamespace(
            id=12, title="热力学", course_name="物理", session_number=1,
        )
        sentences = [{
            "sentence_order": 4,
            "source_text": "Entropy is disorder.",
            "translated_text": "熵是无序。",
            "start_offset_ms": 1000,
            "tag": "definition",
        }]
        db = MagicMock()
        with patch("services.tools.notebook.load_sentence_rows", return_value=sentences), \
             patch("services.tools.notebook.get_briefing", return_value=None), \
             patch("services.tools.notebook.list_attachments", return_value=[]):
            result = search_notebook(db, [lecture], 1, query="熵是什么")
        self.assertEqual(result["tool"], "search_notebook")
        self.assertGreaterEqual(result["count"], 1)
        self.assertEqual(result["hits"][0]["ref"], "L12S4")

    def test_list_and_breakdown_assignment(self):
        lecture = SimpleNamespace(
            id=12, title="热力学", course_name="物理", session_number=1,
        )
        briefing_row = SimpleNamespace(status="ready")
        briefing = {
            "assignments": [{
                "text": "完成第3章习题 1-5",
                "source_text": "Finish problems 1-5",
                "sentence_order": 9,
                "start_offset_ms": 2000,
                "needs_confirmation": False,
                "source": "auto",
            }],
            "key_points": [],
            "exam_hints": [],
            "questions": [],
            "overview": "",
        }
        db = MagicMock()
        with patch("services.tools.notebook.get_briefing", return_value=briefing_row), \
             patch("services.tools.notebook.briefing_to_dict", return_value=briefing), \
             patch("services.tools.notebook.list_attachments", return_value=[]), \
             patch("services.tools.notebook.load_sentence_rows", return_value=[{
                 "sentence_order": 9,
                 "source_text": "Finish problems 1-5",
                 "translated_text": "完成第3章习题 1-5",
                 "start_offset_ms": 2000,
                 "tag": "exam",
             }]):
            listed = list_assignments(db, [lecture], 1)
            self.assertEqual(listed["count"], 1)
            self.assertEqual(listed["assignments"][0]["assignment_id"], "L12A0")
            broken = breakdown_assignment(db, [lecture], 1, assignment_id="L12A0")
        self.assertTrue(broken["found"])
        self.assertGreaterEqual(len(broken["steps_hint"]), 3)


class AgentHelpersTests(unittest.TestCase):
    def test_public_tool_result_search(self):
        card = _public_tool_result("search_notebook", {
            "count": 1,
            "hits": [{"ref": "L1S2", "translated_text": "定义"}],
        })
        self.assertEqual(card["label"], "笔记检索")
        self.assertEqual(card["hits"][0]["ref"], "L1S2")

    def test_template_list_assignments(self):
        template = _template_from_tools(
            "有哪些作业",
            [{
                "name": "list_assignments",
                "result": {
                    "assignments": [{
                        "assignment_id": "L12A0",
                        "text": "习题",
                        "needs_confirmation": True,
                    }],
                    "citations": [],
                },
            }],
            [],
        )
        self.assertIn("L12A0", template["answer"])
        self.assertIn("list_assignments", template["tools_used"])


if __name__ == "__main__":
    unittest.main()

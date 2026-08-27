"""笔记检索、作业列表与作业拆解工具。

工具在服务端执行，不消耗 LLM token；返回体刻意截断，控制后续上送体积。
"""
from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from services.assistant import _citation, _tokens, retrieve_sentences
from services.attachments import list_attachments
from services.briefing import briefing_to_dict, get_briefing, load_sentence_rows


_MAX_SEARCH_HITS = 8
_MAX_SNIPPET = 160
_MAX_ASSIGNMENTS = 20
_ASSIGNMENT_ID_RE = re.compile(r"^L(\d+)A(\d+)$", re.IGNORECASE)
_BREAKDOWN_RE = re.compile(r"(拆解|分解|怎么做|步骤|如何完成|帮我做|怎么写)")
_ASSIGNMENT_RE = re.compile(
    r"(作业|homework|assignment|due|提交|ddl|截止日期|通知)",
    re.IGNORECASE,
)
_SEARCH_RE = re.compile(
    r"(原话|原文|讲了|讲什么|考点|定义|什么是|怎么说|笔记|检索|哪里提到|提到过)",
    re.IGNORECASE,
)
_OVERVIEW_RE = re.compile(r"(有哪些材料|材料盘点|本课材料|有什么笔记|资源概览)")


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_notebook",
            "description": "在所选课次的字幕、简报要点和附件标题中检索课堂证据。问出处、概念、原话时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词或问题"},
                    "limit": {"type": "integer", "description": "最多返回条数，默认 8"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_assignments",
            "description": "列出所选课次简报与附件中的作业/通知，含人工补充项。",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_unconfirmed": {
                        "type": "boolean",
                        "description": "是否包含待确认项，默认 true",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "breakdown_assignment",
            "description": "按作业编号拆解学习步骤，不代写答卷。assignment_id 形如 L12A0。",
            "parameters": {
                "type": "object",
                "properties": {
                    "assignment_id": {
                        "type": "string",
                        "description": "作业编号，格式 L{lecture_id}A{index}",
                    },
                    "focus": {
                        "type": "string",
                        "description": "可选：学生特别关心的部分",
                    },
                },
                "required": ["assignment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_notebook_overview",
            "description": "盘点所选课次的转录句数、简报与附件概况。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def make_assignment_id(lecture_id: int, index: int) -> str:
    return f"L{int(lecture_id)}A{int(index)}"


def parse_assignment_id(value: str) -> Optional[tuple[int, int]]:
    match = _ASSIGNMENT_ID_RE.match((value or "").strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _clip(text: Any, limit: int = _MAX_SNIPPET) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


def _lecture_meta(lecture) -> dict:
    return {
        "lecture_id": int(lecture.id),
        "lecture_title": getattr(lecture, "title", None)
        or getattr(lecture, "course_name", None)
        or "课堂记录",
        "session_number": getattr(lecture, "session_number", None),
    }


def _content_owner_id(lecture, fallback_user_id: int) -> int:
    """公开课证据属于课主；配额仍记在提问用户上。"""
    try:
        return int(getattr(lecture, "user_id", fallback_user_id) or fallback_user_id)
    except (TypeError, ValueError):
        return int(fallback_user_id)


def _load_scope_sentences(db: Session, lectures: list, user_id: int) -> list[dict]:
    sentences: list[dict] = []
    for lecture in lectures:
        meta = _lecture_meta(lecture)
        for row in load_sentence_rows(db, lecture.id, _content_owner_id(lecture, user_id)):
            row = dict(row)
            row.update(meta)
            sentences.append(row)
    return sentences


def _briefing_rows(db: Session, lectures: list, user_id: int) -> list[tuple[Any, dict]]:
    rows = []
    for lecture in lectures:
        try:
            row = get_briefing(db, lecture.id, _content_owner_id(lecture, user_id))
        except Exception:
            continue
        if not row or row.status not in {"ready", "empty"}:
            continue
        data = briefing_to_dict(row)
        rows.append((lecture, data))
    return rows


def _score_text(query_tokens: set[str], text: str) -> int:
    if not query_tokens or not text:
        return 0
    return len(query_tokens & _tokens(text))


def search_notebook(db: Session, lectures: list, user_id: int, *,
                    query: str, limit: int = _MAX_SEARCH_HITS) -> dict:
    """跨字幕 / 简报 / 附件标题检索，返回压缩证据。"""
    query = (query or "").strip()
    limit = max(1, min(int(limit or _MAX_SEARCH_HITS), _MAX_SEARCH_HITS))
    sentences = _load_scope_sentences(db, lectures, user_id)
    intent, hits = retrieve_sentences(query, sentences, {}, limit=limit)
    evidence = []
    for item in hits:
        citation = _citation(item)
        evidence.append({
            "kind": "sentence",
            "ref": f"L{item.get('lecture_id', 0)}S{item['sentence_order']}",
            "lecture_id": item.get("lecture_id"),
            "lecture_title": item.get("lecture_title"),
            "session_number": item.get("session_number"),
            "sentence_order": item.get("sentence_order"),
            "start_offset_ms": item.get("start_offset_ms") or 0,
            "tag": item.get("tag"),
            "source_text": _clip(item.get("source_text")),
            "translated_text": _clip(item.get("translated_text")),
            "citation": citation,
        })

    query_tokens = _tokens(query)
    extras = []
    try:
        for lecture, briefing in _briefing_rows(db, lectures, user_id):
            meta = _lecture_meta(lecture)
            for section in ("key_points", "exam_hints", "questions", "assignments"):
                for index, item in enumerate(briefing.get(section) or []):
                    text = item.get("text") or item.get("term") or item.get("explanation") or ""
                    score = _score_text(query_tokens, text)
                    if score <= 0 and intent != "overview":
                        continue
                    extras.append((score, {
                        "kind": "briefing",
                        "section": section,
                        "index": index,
                        "ref": f"L{meta['lecture_id']}B{section[:1].upper()}{index}",
                        **meta,
                        "text": _clip(text),
                        "sentence_order": item.get("sentence_order"),
                        "start_offset_ms": item.get("start_offset_ms") or 0,
                    }))
            try:
                attachments = list_attachments(db, lecture.id, _content_owner_id(lecture, user_id))
            except Exception:
                attachments = []
            for attachment in attachments:
                blob = f"{attachment.title} {attachment.category}"
                score = _score_text(query_tokens, blob)
                if score <= 0:
                    continue
                extras.append((score, {
                    "kind": "attachment",
                    "ref": f"L{meta['lecture_id']}F{attachment.id}",
                    **meta,
                    "attachment_id": attachment.id,
                    "category": attachment.category,
                    "title": _clip(attachment.title, 80),
                    "url": attachment.url,
                }))
    except Exception:
        extras = []
    extras.sort(key=lambda item: (-item[0], item[1].get("lecture_id") or 0))
    for _, item in extras:
        if len(evidence) >= limit:
            break
        evidence.append(item)

    return {
        "tool": "search_notebook",
        "query": query,
        "intent": intent,
        "count": len(evidence),
        "hits": evidence,
        "citations": [item["citation"] for item in evidence if item.get("citation")],
    }


def list_assignments(db: Session, lectures: list, user_id: int, *,
                     include_unconfirmed: bool = True) -> dict:
    items = []
    for lecture in lectures:
        meta = _lecture_meta(lecture)
        try:
            row = get_briefing(db, lecture.id, _content_owner_id(lecture, user_id))
        except Exception:
            row = None
        briefing = briefing_to_dict(row) if row and row.status in {"ready", "empty"} else {}
        for index, raw in enumerate(briefing.get("assignments") or []):
            needs = bool(raw.get("needs_confirmation"))
            if needs and not include_unconfirmed:
                continue
            items.append({
                "assignment_id": make_assignment_id(lecture.id, index),
                "source": raw.get("source") or "auto",
                "needs_confirmation": needs,
                "text": _clip(raw.get("text") or raw.get("source_text") or "", 240),
                "sentence_order": raw.get("sentence_order"),
                "start_offset_ms": raw.get("start_offset_ms") or 0,
                "due_date": raw.get("due_date"),
                **meta,
            })
            if len(items) >= _MAX_ASSIGNMENTS:
                break
        if len(items) >= _MAX_ASSIGNMENTS:
            break
        try:
            attachments = list_attachments(db, lecture.id, _content_owner_id(lecture, user_id), category="assignment")
        except Exception:
            attachments = []
        for attachment in attachments:
            if len(items) >= _MAX_ASSIGNMENTS:
                break
            items.append({
                "assignment_id": f"L{lecture.id}F{attachment.id}",
                "source": "attachment",
                "needs_confirmation": False,
                "text": _clip(attachment.title, 240),
                "attachment_id": attachment.id,
                "url": attachment.url,
                "sentence_order": None,
                "start_offset_ms": 0,
                "due_date": None,
                **meta,
            })
    return {
        "tool": "list_assignments",
        "count": len(items),
        "assignments": items,
    }


def breakdown_assignment(db: Session, lectures: list, user_id: int, *,
                         assignment_id: str, focus: str = "") -> dict:
    """返回作业正文与相关笔记证据；步骤由上层模型基于该结果生成。"""
    wanted = (assignment_id or "").strip()
    parsed = parse_assignment_id(wanted)
    listed = list_assignments(db, lectures, user_id, include_unconfirmed=True)
    target = None
    if parsed:
        lecture_id, index = parsed
        expected = make_assignment_id(lecture_id, index)
        for item in listed["assignments"]:
            if item.get("assignment_id") == expected:
                target = item
                break
    if target is None:
        for item in listed["assignments"]:
            if item.get("assignment_id") == wanted:
                target = item
                break
    if target is None:
        return {
            "tool": "breakdown_assignment",
            "found": False,
            "assignment_id": wanted,
            "message": "未找到该作业。请先调用 list_assignments 确认编号。",
            "assignments": listed["assignments"][:8],
            "related_hits": [],
            "citations": [],
            "steps_hint": [],
        }

    query = " ".join(
        part for part in [target.get("text") or "", focus or ""] if part
    ).strip() or "作业"
    related = search_notebook(db, lectures, user_id, query=query, limit=5)
    text = target.get("text") or ""
    steps_hint = [
        "确认题目要求与提交形式（书面 / 口头 / 平台）。",
        "从课堂笔记中定位相关定义与例题。",
        "按要点列出作答提纲，不直接代写完整答卷。",
        "对照考点/作业原文检查是否遗漏条件。",
    ]
    if "阅读" in text or "reading" in text.lower():
        steps_hint[1] = "先完成指定阅读，再摘录与课堂对应的概念。"
    if focus:
        steps_hint.insert(1, f"优先处理学生关注点：{_clip(focus, 80)}")
    return {
        "tool": "breakdown_assignment",
        "found": True,
        "assignment": target,
        "related_hits": related.get("hits") or [],
        "citations": related.get("citations") or [],
        "steps_hint": steps_hint,
        "policy": "只拆解步骤与复习路径，禁止代写完整答卷或可直接提交的答案全文。",
    }


def get_notebook_overview(db: Session, lectures: list, user_id: int) -> dict:
    lectures_out = []
    for lecture in lectures:
        meta = _lecture_meta(lecture)
        owner_id = _content_owner_id(lecture, user_id)
        try:
            sentences = load_sentence_rows(db, lecture.id, owner_id)
        except Exception:
            sentences = []
        try:
            row = get_briefing(db, lecture.id, owner_id)
        except Exception:
            row = None
        briefing = briefing_to_dict(row) if row and row.status in {"ready", "empty"} else {}
        try:
            attachments = list_attachments(db, lecture.id, owner_id)
        except Exception:
            attachments = []
        lectures_out.append({
            **meta,
            "sentence_count": len(sentences),
            "has_briefing": bool(briefing.get("overview") or briefing.get("key_points")),
            "assignment_count": len(briefing.get("assignments") or []),
            "attachment_count": len(attachments),
            "attachment_categories": sorted({item.category for item in attachments}),
        })
    return {
        "tool": "get_notebook_overview",
        "lecture_count": len(lectures_out),
        "lectures": lectures_out,
    }


def suggest_tools(question: str, *, hint: Optional[str] = None,
                  assignment_id: Optional[str] = None) -> list[dict]:
    """无模型时的轻量路由；也用于芯片强制意图。"""
    text = (question or "").strip()
    forced = (hint or "").strip()
    if assignment_id and forced in {"", "breakdown_assignment"}:
        return [{"name": "breakdown_assignment", "arguments": {
            "assignment_id": assignment_id,
            "focus": text[:120],
        }}]
    if forced == "search_notebook":
        return [{"name": "search_notebook", "arguments": {"query": text or "课堂重点"}}]
    if forced == "list_assignments":
        return [{"name": "list_assignments", "arguments": {"include_unconfirmed": True}}]
    if forced == "breakdown_assignment":
        calls = [{"name": "list_assignments", "arguments": {"include_unconfirmed": True}}]
        if assignment_id:
            calls = [{"name": "breakdown_assignment", "arguments": {
                "assignment_id": assignment_id, "focus": text[:120],
            }}]
        return calls
    if forced == "get_notebook_overview":
        return [{"name": "get_notebook_overview", "arguments": {}}]

    if _OVERVIEW_RE.search(text):
        return [{"name": "get_notebook_overview", "arguments": {}}]
    if _BREAKDOWN_RE.search(text) and _ASSIGNMENT_RE.search(text):
        return [
            {"name": "list_assignments", "arguments": {"include_unconfirmed": True}},
        ]
    if _ASSIGNMENT_RE.search(text):
        return [{"name": "list_assignments", "arguments": {"include_unconfirmed": True}}]
    if _SEARCH_RE.search(text) or len(_tokens(text)) >= 2:
        return [{"name": "search_notebook", "arguments": {"query": text}}]
    return []


def execute_tool(db: Session, lectures: list, user_id: int, name: str,
                 arguments: Optional[dict] = None) -> dict:
    args = arguments if isinstance(arguments, dict) else {}
    if name == "search_notebook":
        return search_notebook(
            db, lectures, user_id,
            query=str(args.get("query") or ""),
            limit=int(args.get("limit") or _MAX_SEARCH_HITS),
        )
    if name == "list_assignments":
        return list_assignments(
            db, lectures, user_id,
            include_unconfirmed=bool(args.get("include_unconfirmed", True)),
        )
    if name == "breakdown_assignment":
        return breakdown_assignment(
            db, lectures, user_id,
            assignment_id=str(args.get("assignment_id") or ""),
            focus=str(args.get("focus") or ""),
        )
    if name == "get_notebook_overview":
        return get_notebook_overview(db, lectures, user_id)
    return {"tool": name, "error": f"未知工具: {name}"}

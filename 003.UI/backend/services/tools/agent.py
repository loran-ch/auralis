"""课程助手工具调用循环：先取证据，再流式生成回答。"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

import requests

from config import (BRIEFING_LLM_API_KEY, BRIEFING_LLM_API_URL,
                    BRIEFING_LLM_MODEL, BRIEFING_LLM_TIMEOUT_SECONDS)
from services.assistant import (_MAX_HISTORY, _SUPPLEMENT_RULES,
                                _iter_text_chunks, _merge_scope_stream_answer,
                                build_template_answer, retrieve_sentences)
from services.briefing import load_sentence_rows
from services.llm_quota import (QuotaExceededError, assert_within_quota,
                                estimate_tokens_from_text, parse_usage_from_response,
                                record_usage)
from services.tools.notebook import (TOOL_DEFINITIONS, execute_tool,
                                     suggest_tools)


logger = logging.getLogger(__name__)

_MAX_TOOL_CALLS = 2
_TOOL_RESULT_CHARS = 3500
_ALLOWED_TOOLS = {item["function"]["name"] for item in TOOL_DEFINITIONS}
_TOOL_CHOICE_SYSTEM = (
    "你是课堂学习助手的工具调度器。根据学生问题决定是否调用工具。"
    "问出处/概念/原话 → search_notebook；"
    "问有哪些作业 → list_assignments；"
    "要拆解某项作业 → breakdown_assignment（需 assignment_id）或先 list_assignments；"
    "问本课有哪些材料 → get_notebook_overview。"
    "闲聊或不需要课堂证据时不要调用工具。"
    "最多调用 2 个工具。"
)
_ANSWER_SYSTEM = (
    "你是严谨的课堂学习助手。"
    + _SUPPLEMENT_RULES
    + "若工具返回了作业列表，请用 assignment_id 引用。"
    + "拆解作业时只给步骤与复习路径，禁止代写完整可提交答卷。"
    + "不要输出 JSON、Markdown 代码块或单独的引用列表。"
)


def _compact_history(history: Optional[list[dict]]) -> list[dict]:
    compact = []
    for item in (history or [])[-_MAX_HISTORY:]:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            compact.append({"role": role, "content": content[:400]})
    return compact


def _trim_tool_payload(payload: dict) -> dict:
    text = json.dumps(payload, ensure_ascii=False)
    if len(text) <= _TOOL_RESULT_CHARS:
        return payload
    slim = dict(payload)
    if isinstance(slim.get("hits"), list):
        slim["hits"] = slim["hits"][:5]
    if isinstance(slim.get("related_hits"), list):
        slim["related_hits"] = slim["related_hits"][:4]
    if isinstance(slim.get("assignments"), list):
        slim["assignments"] = slim["assignments"][:10]
    if isinstance(slim.get("citations"), list):
        slim["citations"] = slim["citations"][:8]
    text = json.dumps(slim, ensure_ascii=False)
    if len(text) > _TOOL_RESULT_CHARS:
        slim["truncated"] = True
        slim["preview"] = text[: _TOOL_RESULT_CHARS - 40] + "…"
        for key in ("hits", "related_hits", "assignments", "lectures", "citations"):
            if key in slim and key != "preview":
                slim[key] = (slim.get(key) or [])[:3]
    return slim


def _public_tool_result(name: str, payload: dict) -> dict:
    """前端展示用的精简卡片，避免把大段 JSON 塞进气泡。"""
    if name == "search_notebook":
        return {
            "tool": name,
            "label": "笔记检索",
            "count": payload.get("count") or len(payload.get("hits") or []),
            "hits": [
                {
                    "ref": item.get("ref"),
                    "lecture_title": item.get("lecture_title"),
                    "text": item.get("translated_text") or item.get("source_text") or item.get("text") or item.get("title"),
                }
                for item in (payload.get("hits") or [])[:5]
            ],
        }
    if name == "list_assignments":
        return {
            "tool": name,
            "label": "作业列表",
            "count": payload.get("count") or len(payload.get("assignments") or []),
            "assignments": [
                {
                    "assignment_id": item.get("assignment_id"),
                    "text": item.get("text"),
                    "lecture_title": item.get("lecture_title"),
                    "needs_confirmation": item.get("needs_confirmation"),
                }
                for item in (payload.get("assignments") or [])[:8]
            ],
        }
    if name == "breakdown_assignment":
        assignment = payload.get("assignment") or {}
        return {
            "tool": name,
            "label": "作业拆解",
            "found": payload.get("found"),
            "assignment_id": assignment.get("assignment_id") or payload.get("assignment_id"),
            "text": assignment.get("text") or payload.get("message"),
            "steps_hint": payload.get("steps_hint") or [],
            "related_count": len(payload.get("related_hits") or []),
        }
    if name == "get_notebook_overview":
        return {
            "tool": name,
            "label": "材料盘点",
            "lecture_count": payload.get("lecture_count"),
            "lectures": payload.get("lectures") or [],
        }
    return {"tool": name, "label": name, "ok": "error" not in payload}


def _normalize_tool_calls(raw_calls: Any) -> list[dict]:
    calls = []
    if not isinstance(raw_calls, list):
        return calls
    for item in raw_calls[:_MAX_TOOL_CALLS]:
        if not isinstance(item, dict):
            continue
        function = item.get("function") if isinstance(item.get("function"), dict) else item
        name = str(function.get("name") or "").strip()
        if name not in _ALLOWED_TOOLS:
            continue
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        calls.append({"name": name, "arguments": arguments})
    return calls


def _llm_choose_tools(question: str, scope_name: str, summary: str,
                      history: list[dict], *, db=None, user_id: Optional[int] = None) -> list[dict]:
    """尝试让模型选工具；失败则返回空，由启发式兜底。"""
    if not (BRIEFING_LLM_API_URL and BRIEFING_LLM_API_KEY):
        return []
    body = {
        "model": BRIEFING_LLM_MODEL,
        "temperature": 0,
        "tools": TOOL_DEFINITIONS,
        "tool_choice": "auto",
        "messages": [
            {"role": "system", "content": _TOOL_CHOICE_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"查询范围：{scope_name}\n"
                    f"较早会话摘要：{summary or '（无）'}\n"
                    f"最近对话：{json.dumps(history, ensure_ascii=False)}\n"
                    f"学生问题：{question}\n"
                    "如需工具请直接 function call；否则不要调用。"
                ),
            },
        ],
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BRIEFING_LLM_API_KEY}",
        "User-Agent": "LiveTrans/1.4",
    }
    try:
        response = requests.post(
            BRIEFING_LLM_API_URL,
            json=body,
            headers=headers,
            timeout=min(BRIEFING_LLM_TIMEOUT_SECONDS, 30),
        )
        data = response.json()
        if not response.ok:
            raise RuntimeError(str(data)[:200])
        if db is not None and user_id is not None:
            usage = parse_usage_from_response(
                data,
                prompt_hint=json.dumps(body["messages"], ensure_ascii=False),
            )
            record_usage(
                db,
                user_id=user_id,
                source="assistant_tools",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )
        message = data["choices"][0].get("message") or {}
        return _normalize_tool_calls(message.get("tool_calls"))
    except Exception as exc:
        logger.info("工具选择模型不可用，改用启发式: %s", exc)
        return []


def _collect_citations(tool_results: list[dict]) -> list[dict]:
    citations = []
    seen = set()
    for payload in tool_results:
        for item in payload.get("citations") or []:
            key = (item.get("lecture_id"), item.get("sentence_order"))
            if key in seen:
                continue
            seen.add(key)
            citations.append(item)
        for hit in payload.get("hits") or []:
            citation = hit.get("citation")
            if not citation:
                continue
            key = (citation.get("lecture_id"), citation.get("sentence_order"))
            if key in seen:
                continue
            seen.add(key)
            citations.append(citation)
        for hit in payload.get("related_hits") or []:
            citation = hit.get("citation")
            if not citation:
                continue
            key = (citation.get("lecture_id"), citation.get("sentence_order"))
            if key in seen:
                continue
            seen.add(key)
            citations.append(citation)
    return citations


def _hits_from_tool_results(tool_results: list[dict]) -> list[dict]:
    hits = []
    seen = set()
    for payload in tool_results:
        for bucket in (payload.get("hits"), payload.get("related_hits")):
            for item in bucket or []:
                if item.get("kind") and item.get("kind") != "sentence":
                    continue
                if "sentence_order" not in item:
                    continue
                key = (item.get("lecture_id"), item.get("sentence_order"))
                if key in seen:
                    continue
                seen.add(key)
                hits.append(item)
    return hits


def _stream_final_answer(question: str, scope_name: str, summary: str,
                         history: list[dict], tool_packets: list[dict]):
    compact_tools = [
        {"name": item["name"], "result": _trim_tool_payload(item["result"])}
        for item in tool_packets
    ]
    user_prompt = (
        f"查询范围：{scope_name}\n"
        f"较早会话摘要：{summary or '（无）'}\n"
        f"最近对话：{json.dumps(history, ensure_ascii=False)}\n"
        f"工具结果：{json.dumps(compact_tools, ensure_ascii=False)}\n"
        f"学生问题：{question}\n"
        "请基于工具结果回答。"
    )
    body = {
        "model": BRIEFING_LLM_MODEL,
        "temperature": 0.2,
        "stream": True,
        "messages": [
            {"role": "system", "content": _ANSWER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BRIEFING_LLM_API_KEY}",
        "User-Agent": "LiveTrans/1.4",
    }
    timeout = (10, max(BRIEFING_LLM_TIMEOUT_SECONDS, 60))
    with requests.post(
        BRIEFING_LLM_API_URL,
        json=body,
        headers=headers,
        timeout=timeout,
        stream=True,
    ) as response:
        if not response.ok:
            try:
                detail = response.json()
            except ValueError:
                detail = response.content[:200].decode("utf-8", errors="replace")
            raise RuntimeError(str(detail)[:200])
        response.encoding = "utf-8"
        for raw_line in response.iter_lines(decode_unicode=False):
            if not raw_line:
                continue
            if isinstance(raw_line, bytes):
                line = raw_line.decode("utf-8", errors="replace").strip()
            else:
                line = str(raw_line).strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
                delta = event["choices"][0].get("delta") or {}
                content = delta.get("content") or ""
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if isinstance(content, str) and content:
                yield content


def _template_from_tools(question: str, tool_packets: list[dict],
                         sentences: list[dict]) -> dict:
    hits = _hits_from_tool_results([item["result"] for item in tool_packets])
    if not hits and sentences:
        _, hits = retrieve_sentences(question, sentences, {}, limit=5)
    intent = "search"
    for packet in tool_packets:
        if packet["name"] == "list_assignments":
            intent = "exam"
            assignments = packet["result"].get("assignments") or []
            if not assignments:
                return {
                    "answer": "所选范围内还没有识别到作业/通知。可在回顾页人工补充或上传作业附件。",
                    "citations": [],
                    "provider": "extractive",
                    "used_briefing": False,
                    "tools_used": [item["name"] for item in tool_packets],
                }
            lines = ["当前范围内的作业/通知："]
            for item in assignments[:10]:
                flag = "（待确认）" if item.get("needs_confirmation") else ""
                lines.append(
                    f"- {item.get('assignment_id')} {item.get('text') or ''}{flag}"
                )
            lines.append("若要拆解某一项，可以说「拆解 LxxA0」或点击作业旁的拆解入口。")
            return {
                "answer": "\n".join(lines),
                "citations": _collect_citations([item["result"] for item in tool_packets]),
                "provider": "extractive",
                "used_briefing": True,
                "tools_used": [item["name"] for item in tool_packets],
            }
        if packet["name"] == "breakdown_assignment":
            result = packet["result"]
            if not result.get("found"):
                return {
                    "answer": result.get("message") or "未找到该作业。",
                    "citations": [],
                    "provider": "extractive",
                    "used_briefing": False,
                    "tools_used": [item["name"] for item in tool_packets],
                }
            assignment = result.get("assignment") or {}
            lines = [
                f"作业 {assignment.get('assignment_id')}：{assignment.get('text') or ''}",
                "",
                "建议步骤：",
            ]
            for index, step in enumerate(result.get("steps_hint") or [], start=1):
                lines.append(f"{index}. {step}")
            related = result.get("related_hits") or []
            if related:
                lines.append("")
                lines.append("相关课堂证据：")
                for item in related[:4]:
                    ref = item.get("ref") or ""
                    text = item.get("translated_text") or item.get("text") or ""
                    lines.append(f"- [{ref}] {text}")
            lines.append("")
            lines.append("（以上为学习路径拆解，不是可直接提交的完整答卷。）")
            return {
                "answer": "\n".join(lines),
                "citations": result.get("citations") or [],
                "provider": "extractive",
                "used_briefing": True,
                "tools_used": [item["name"] for item in tool_packets],
            }
        if packet["name"] == "get_notebook_overview":
            lectures = packet["result"].get("lectures") or []
            if not lectures:
                return {
                    "answer": "所选范围内还没有课堂材料。",
                    "citations": [],
                    "provider": "extractive",
                    "used_briefing": False,
                    "tools_used": [item["name"] for item in tool_packets],
                }
            lines = ["本范围内材料概览："]
            for item in lectures:
                title = item.get("lecture_title") or "课堂记录"
                lines.append(
                    f"- {title}：字幕 {item.get('sentence_count', 0)} 句，"
                    f"作业 {item.get('assignment_count', 0)} 项，"
                    f"附件 {item.get('attachment_count', 0)} 个"
                )
            return {
                "answer": "\n".join(lines),
                "citations": [],
                "provider": "extractive",
                "used_briefing": True,
                "tools_used": [item["name"] for item in tool_packets],
            }
    template = build_template_answer(question, intent, hits, {})
    template["used_briefing"] = False
    template["tools_used"] = [item["name"] for item in tool_packets]
    return template


def stream_with_tools(db, lectures: list, user_id: int, question: str, *,
                      scope_name: str = "课堂记录",
                      history: Optional[list[dict]] = None,
                      summary: str = "",
                      hint: Optional[str] = None,
                      assignment_id: Optional[str] = None,
                      image_ocr: Optional[str] = None):
    """产出 tool_start / tool_result / delta / done。"""
    sentences: list[dict] = []
    for lecture in lectures:
        rows = load_sentence_rows(db, lecture.id, int(lecture.user_id))
        lecture_title = getattr(lecture, "title", None) or getattr(lecture, "course_name", "课堂记录")
        for row in rows:
            row = dict(row)
            row["lecture_id"] = lecture.id
            row["lecture_title"] = lecture_title
            row["session_number"] = getattr(lecture, "session_number", None)
            sentences.append(row)

    if not sentences and not lectures:
        empty = {
            "answer": "所选范围内还没有可用的课堂转录，暂时无法回答。",
            "citations": [], "provider": "extractive", "used_briefing": False,
            "tools_used": [],
        }
        for chunk in _iter_text_chunks(empty["answer"]):
            yield {"type": "delta", "content": chunk}
        yield {"type": "done", "result": empty}
        return

    compact_history = _compact_history(history)
    effective_hint = hint
    if image_ocr and not effective_hint and not assignment_id:
        # 截图提问默认先检索笔记，避免把报错截图误判成闲聊。
        effective_hint = "search_notebook"
    llm_allowed = bool(BRIEFING_LLM_API_URL and BRIEFING_LLM_API_KEY)
    if llm_allowed:
        try:
            assert_within_quota(db, user_id)
        except QuotaExceededError as exc:
            msg = str(exc)
            for chunk in _iter_text_chunks(msg):
                yield {"type": "delta", "content": chunk}
            yield {
                "type": "done",
                "result": {
                    "answer": msg,
                    "citations": [],
                    "provider": "quota",
                    "used_briefing": False,
                    "tools_used": [],
                },
            }
            return

    tool_calls = suggest_tools(question, hint=effective_hint, assignment_id=assignment_id)
    if not tool_calls and not effective_hint and llm_allowed:
        model_calls = _llm_choose_tools(
            question, scope_name, summary, compact_history, db=db, user_id=user_id,
        )
        if model_calls:
            tool_calls = model_calls
        elif sentences:
            tool_calls = [{"name": "search_notebook", "arguments": {"query": question}}]

    if image_ocr:
        display_part = re.split(r"【截图", question or "", maxsplit=1)[0].strip()
        compact_query = " ".join(part for part in [display_part, str(image_ocr)[:300]] if part)[:400]
        for call in tool_calls:
            if call.get("name") == "search_notebook":
                args = dict(call.get("arguments") or {})
                args["query"] = compact_query or args.get("query") or question[:400]
                call["arguments"] = args

    tool_packets = []
    for call in tool_calls[:_MAX_TOOL_CALLS]:
        name = call["name"]
        arguments = call.get("arguments") or {}
        yield {"type": "tool_start", "tool": name, "arguments": arguments}
        result = execute_tool(db, lectures, user_id, name, arguments)
        tool_packets.append({"name": name, "arguments": arguments, "result": result})
        yield {
            "type": "tool_result",
            "tool": name,
            "result": _public_tool_result(name, result),
        }

        # 拆解意图但只拿到列表时，若问题像拆解且仅有 1 项，自动跟一次 breakdown。
        if (
            name == "list_assignments"
            and len(tool_packets) < _MAX_TOOL_CALLS
            and re.search(r"(拆解|分解|步骤|怎么做)", question or "")
        ):
            assignments = result.get("assignments") or []
            if len(assignments) == 1 and assignments[0].get("assignment_id"):
                follow = {
                    "name": "breakdown_assignment",
                    "arguments": {
                        "assignment_id": assignments[0]["assignment_id"],
                        "focus": question[:120],
                    },
                }
                yield {"type": "tool_start", "tool": follow["name"], "arguments": follow["arguments"]}
                follow_result = execute_tool(
                    db, lectures, user_id, follow["name"], follow["arguments"],
                )
                tool_packets.append({
                    "name": follow["name"],
                    "arguments": follow["arguments"],
                    "result": follow_result,
                })
                yield {
                    "type": "tool_result",
                    "tool": follow["name"],
                    "result": _public_tool_result(follow["name"], follow_result),
                }

    template = _template_from_tools(question, tool_packets, sentences)
    hits = _hits_from_tool_results([item["result"] for item in tool_packets])
    if not (BRIEFING_LLM_API_URL and BRIEFING_LLM_API_KEY):
        for chunk in _iter_text_chunks(template["answer"]):
            yield {"type": "delta", "content": chunk}
        yield {"type": "done", "result": template}
        return

    chunks = []
    try:
        for content in _stream_final_answer(
            question, scope_name, summary, compact_history, tool_packets,
        ):
            chunks.append(content)
            yield {"type": "delta", "content": content}
        answer_text = "".join(chunks)
        result = _merge_scope_stream_answer(template, answer_text, hits)
        if not chunks and result.get("answer"):
            for chunk in _iter_text_chunks(result["answer"]):
                yield {"type": "delta", "content": chunk}
        result["tools_used"] = [item["name"] for item in tool_packets]
        if not result.get("citations"):
            result["citations"] = template.get("citations") or _collect_citations(
                [item["result"] for item in tool_packets]
            )
        if answer_text or result.get("answer"):
            total = estimate_tokens_from_text(question, answer_text or result.get("answer") or "")
            record_usage(
                db,
                user_id=user_id,
                source="assistant",
                prompt_tokens=total,
                completion_tokens=0,
                total_tokens=total,
            )
    except Exception as exc:
        logger.warning("工具化助手流式失败，回退模板: %s", exc)
        result = template
        if not chunks:
            for chunk in _iter_text_chunks(result["answer"]):
                yield {"type": "delta", "content": chunk}
    yield {"type": "done", "result": result}

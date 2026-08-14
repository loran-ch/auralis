"""LiveTrans Voice — 课后课堂助教问答。

只检索本堂转录和收藏，回答必须引用真实 sentence_order。
未配置 LLM 时使用模板回答；配置后仅基于检索证据生成。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import requests

from config import (BRIEFING_LLM_API_KEY, BRIEFING_LLM_API_URL,
                    BRIEFING_LLM_MODEL, BRIEFING_LLM_TIMEOUT_SECONDS)
from services.briefing import (briefing_to_dict, get_briefing,
                               load_sentence_rows)


logger = logging.getLogger(__name__)

_MAX_HITS = 10
_MAX_HISTORY = 6
_EXAM_RE = re.compile(
    r"(exam|quiz|midterm|final|homework|assignment|考点|考试|作业|期末|期中)",
    re.IGNORECASE,
)
_OVERVIEW_RE = re.compile(r"(讲了什么|讲什么|概述|总结|摘要|简报|这节课|本节课|主要内容)")
_QUOTE_RE = re.compile(r"(原话|原文|怎么说|原句|原词)")
_QUESTION_MARK_RE = re.compile(r"(疑问|不懂|我标|收藏的问|解释我)")
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,}|[\u4e00-\u9fff]{1,}")


def classify_question(question: str) -> str:
    text = (question or "").strip()
    if _QUESTION_MARK_RE.search(text):
        return "bookmarked_questions"
    if _QUOTE_RE.search(text):
        return "quote"
    if _EXAM_RE.search(text):
        return "exam"
    if _OVERVIEW_RE.search(text):
        return "overview"
    return "search"


def _tokens(text: str) -> set[str]:
    return {item.lower() for item in _TOKEN_RE.findall(text or "") if item.strip()}


def _citation(sentence: dict) -> dict:
    return {
        "sentence_order": int(sentence["sentence_order"]),
        "start_offset_ms": int(sentence.get("start_offset_ms") or 0),
        "source_text": sentence.get("source_text") or "",
        "translated_text": sentence.get("translated_text") or "",
        "tag": sentence.get("tag"),
    }


def _unique_hits(items: list[dict], limit: int = _MAX_HITS) -> list[dict]:
    seen = set()
    result = []
    for item in items:
        order = item.get("sentence_order")
        if order in seen:
            continue
        seen.add(order)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def retrieve_sentences(question: str, sentences: list[dict],
                       briefing: Optional[dict] = None,
                       limit: int = _MAX_HITS) -> tuple[str, list[dict]]:
    """按问题类型取证据句。返回 (intent, hits)。"""
    intent = classify_question(question)
    briefing = briefing or {}

    if intent == "overview":
        orders = []
        for item in briefing.get("outline") or []:
            start = item.get("start_order")
            if start is not None:
                orders.append(int(start))
        lookup = {int(row["sentence_order"]): row for row in sentences}
        hits = [lookup[order] for order in orders if order in lookup]
        if not hits:
            hits = sentences[: min(4, len(sentences))]
        return intent, _unique_hits(hits, limit)

    if intent == "exam":
        hits = [
            row for row in sentences
            if row.get("tag") == "exam"
            or _EXAM_RE.search(f"{row.get('source_text', '')} {row.get('translated_text', '')}")
        ]
        return intent, _unique_hits(hits, limit)

    if intent == "bookmarked_questions":
        hits = [row for row in sentences if row.get("tag") == "question"]
        return intent, _unique_hits(hits, limit)

    query_tokens = _tokens(question)
    scored = []
    for row in sentences:
        blob = f"{row.get('source_text', '')} {row.get('translated_text', '')}"
        overlap = len(query_tokens & _tokens(blob))
        if overlap <= 0:
            continue
        score = overlap * 3
        if row.get("tag") in {"important", "definition", "exam"}:
            score += 2
        if intent == "quote":
            score += 1
        scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], item[1]["sentence_order"]))
    hits = [row for _, row in scored[:limit]]
    if intent == "quote" and not hits and sentences:
        hits = sentences[: min(3, len(sentences))]
        return intent, hits
    return intent, hits


def _line(sentence: dict, *, quote: bool = False) -> str:
    order = sentence["sentence_order"]
    translated = (sentence.get("translated_text") or "").strip()
    source = (sentence.get("source_text") or "").strip()
    if quote:
        return f"#{order} 原文：{source}\n译文：{translated}"
    return f"#{order} {translated or source}"


def build_template_answer(question: str, intent: str, hits: list[dict],
                          briefing: Optional[dict] = None) -> dict:
    briefing = briefing or {}
    citations = [_citation(item) for item in hits]

    if intent == "overview":
        overview = (briefing.get("overview") or "").strip()
        if overview:
            answer = overview
        elif hits:
            answer = "根据课堂记录，这节课主要内容如下。"
        else:
            return {
                "answer": "这堂课还没有可用的转录，暂时无法概括讲了什么。",
                "citations": [],
                "provider": "extractive",
            }
        if hits:
            answer += "\n" + "\n".join(_line(item) for item in hits)
        return {"answer": answer, "citations": citations, "provider": "extractive"}

    if intent == "exam":
        if not hits:
            return {
                "answer": "记录里没有明确的考点或考试提示。你可以在字幕上把相关句子标为「考点」。",
                "citations": [],
                "provider": "extractive",
            }
        answer = f"教授在这些句子里强调了考点或作业（共 {len(hits)} 处）：\n"
        answer += "\n".join(_line(item) for item in hits)
        return {"answer": answer, "citations": citations, "provider": "extractive"}

    if intent == "bookmarked_questions":
        if not hits:
            return {
                "answer": "你还没有把句子标为「疑问」。可在下方字幕点星标，选择「疑问」后再问我。",
                "citations": [],
                "provider": "extractive",
            }
        answer = "这些是你标了疑问的句子，对照原文和译文看一下：\n"
        answer += "\n".join(_line(item, quote=True) for item in hits)
        return {"answer": answer, "citations": citations, "provider": "extractive"}

    if intent == "quote":
        if not hits:
            return {
                "answer": "记录里没有找到你说的这个概念。可以换关键词，或指出大概在课堂的哪一段。",
                "citations": [],
                "provider": "extractive",
            }
        answer = "课堂原话如下：\n" + "\n".join(_line(item, quote=True) for item in hits)
        return {"answer": answer, "citations": citations, "provider": "extractive"}

    if not hits:
        return {
            "answer": "记录里没有提到这个问题。我只能根据这堂课已识别的句子回答，不能补充课外内容。",
            "citations": [],
            "provider": "extractive",
        }
    answer = "和这个问题最相关的句子：\n" + "\n".join(_line(item, quote=True) for item in hits)
    return {"answer": answer, "citations": citations, "provider": "extractive"}


def _parse_llm_json(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("助教模型未返回对象")
    return data


def _call_assistant_llm(question: str, course_name: str, overview: str,
                        hits: list[dict], history: list[dict]) -> dict:
    evidence = [
        {
            "order": item["sentence_order"],
            "src": item.get("source_text") or "",
            "dst": item.get("translated_text") or "",
            "tag": item.get("tag"),
        }
        for item in hits
    ]
    compact_history = []
    for item in history[-_MAX_HISTORY:]:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            compact_history.append({"role": role, "content": content[:400]})
    user_prompt = (
        f"课程：{course_name}\n"
        f"简报概述：{overview or '（无）'}\n"
        f"证据句子：{json.dumps(evidence, ensure_ascii=False)}\n"
        f"最近对话：{json.dumps(compact_history, ensure_ascii=False)}\n"
        f"学生问题：{question}\n"
        "只根据证据回答，必须在 answer 里用 #编号 引用句子。"
        "输出 JSON：{\"answer\":\"...\",\"citation_orders\":[3,7]}"
    )
    body = {
        "model": BRIEFING_LLM_MODEL,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是课堂助教。只能使用给定证据句子，禁止编造未出现的内容。"
                    "如果证据不足，就明确说记录里没有提到。必须输出 JSON。"
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BRIEFING_LLM_API_KEY}",
        "User-Agent": "LiveTrans/1.4",
    }
    last_error = None
    for use_json_format in (True, False):
        request_body = dict(body)
        if use_json_format:
            request_body["response_format"] = {"type": "json_object"}
        try:
            response = requests.post(
                BRIEFING_LLM_API_URL,
                json=request_body,
                headers=headers,
                timeout=BRIEFING_LLM_TIMEOUT_SECONDS,
            )
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            continue
        if not response.ok:
            last_error = RuntimeError(str(data)[:200])
            continue
        try:
            content = data["choices"][0]["message"]["content"]
            return _parse_llm_json(content)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
    raise RuntimeError(f"助教大模型不可用: {last_error}")


def merge_llm_answer(template: dict, llm_payload: dict, hits: list[dict]) -> dict:
    lookup = {int(item["sentence_order"]): item for item in hits}
    orders: list[int] = []
    raw_orders = llm_payload.get("citation_orders") or []
    if isinstance(raw_orders, list):
        for value in raw_orders:
            try:
                order = int(value)
            except (TypeError, ValueError):
                continue
            if order in lookup and order not in orders:
                orders.append(order)
    answer = str(llm_payload.get("answer") or "").strip()
    if not answer or not orders:
        return template
    citations = [_citation(lookup[order]) for order in orders]
    return {
        "answer": answer,
        "citations": citations,
        "provider": f"llm:{BRIEFING_LLM_MODEL}",
    }


def answer_lecture_question(
    db,
    lecture_id: int,
    user_id: int,
    question: str,
    history: Optional[list[dict]] = None,
    course_name: str = "",
) -> Optional[dict]:
    sentences = load_sentence_rows(db, lecture_id, user_id)
    row = get_briefing(db, lecture_id, user_id)
    briefing = briefing_to_dict(row) if row and row.status in {"ready", "empty"} else {}
    intent, hits = retrieve_sentences(question, sentences, briefing)
    template = build_template_answer(question, intent, hits, briefing)
    template["used_briefing"] = bool(briefing.get("overview"))
    if not (BRIEFING_LLM_API_URL and BRIEFING_LLM_API_KEY) or not hits:
        return template
    try:
        llm_payload = _call_assistant_llm(
            question, course_name, briefing.get("overview") or "", hits, history or [],
        )
        merged = merge_llm_answer(template, llm_payload, hits)
        merged["used_briefing"] = template["used_briefing"]
        return merged
    except Exception as exc:
        logger.warning("课堂助教大模型失败，回退模板回答: %s", exc)
        return template

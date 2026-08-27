"""LiveTrans Voice — 课堂简报生成。

默认从转录和收藏做抽取式简报，不依赖大模型。
配置 BRIEFING_LLM_API_URL 后，用 OpenAI 兼容接口润色摘要，失败则回退抽取结果。
"""
from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime
from typing import Any, Optional

import requests
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import (BRIEFING_LLM_API_KEY, BRIEFING_LLM_API_URL,
                    BRIEFING_LLM_MODEL, BRIEFING_LLM_TIMEOUT_SECONDS,
                    BRIEFING_MAX_SENTENCES, BRIEFING_STALE_SECONDS)
from database import engine
from models.lecture import Bookmark, Lecture, LectureBriefing, Transcription
from services.llm_quota import (QuotaExceededError, assert_within_quota,
                                parse_usage_from_response, record_usage)


logger = logging.getLogger(__name__)

_TABLE_READY = False
_TABLE_LOCK = threading.Lock()
_OUTLINE_CHUNK = 8
_MAX_KEY_POINTS = 8
_MAX_EXAM = 6
_MAX_QUESTIONS = 6
_MAX_TERMS = 8
_MAX_ASSIGNMENTS = 6
_LLM_CHAR_BUDGET = 14000

_EXAM_PATTERN = re.compile(
    r"(exam|quiz|midterm|final|homework|assignment|remember this|"
    r"will be on|don't forget|make sure you|important for|"
    r"考试|考点|作业|记住|重点|期末|期中|务必|"
    r"Prüfung|Klausur|Hausaufgabe|wichtig|"
    r"examen|devoir|"
    r"試験|宿題|重要)",
    re.IGNORECASE,
)
_QUESTION_PATTERN = re.compile(r"[?？]|why |how |what |请问|为什么|怎么")
_ASSIGNMENT_PATTERN = re.compile(
    r"(homework|assignment|due (?:on|by)|submit|reading (?:for|assignment)|"
    r"read (?:chapter|pages?)|prepare for next|"
    r"作业|作业是|完成.*(?:题|练习)|提交|截止|下节课.*(?:准备|阅读)|预习|阅读.*(?:章|页))",
    re.IGNORECASE,
)
_TERM_PATTERNS = (
    re.compile(r"(?i)(.+?)\s+is defined as\s+(.+)"),
    re.compile(r"(?i)we define\s+(.+?)\s+as\s+(.+)"),
    re.compile(r"(?i)(.+?)\s+(?:is|are) called\s+(.+)"),
    re.compile(r"(.+?)定义为(.+)"),
    re.compile(r"(.+?)是指(.+)"),
    re.compile(r"(?i)the formula (?:for (.+?) )?is\s+(.+)"),
)


def ensure_briefing_table() -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return
    with _TABLE_LOCK:
        if _TABLE_READY:
            return
        LectureBriefing.__table__.create(bind=engine, checkfirst=True)
        _ensure_briefing_edit_columns()
        _TABLE_READY = True


def _ensure_briefing_edit_columns() -> None:
    """兼容已建旧表：补齐人工修订相关列。"""
    statements = {
        "edit_status": (
            "ALTER TABLE lecture_briefings "
            "ADD COLUMN edit_status ENUM('auto','edited') NOT NULL DEFAULT 'auto' AFTER status"
        ),
        "edited_at": (
            "ALTER TABLE lecture_briefings "
            "ADD COLUMN edited_at DATETIME NULL DEFAULT NULL AFTER generated_at"
        ),
        "previous_payload": (
            "ALTER TABLE lecture_briefings "
            "ADD COLUMN previous_payload JSON NULL AFTER error_message"
        ),
    }
    with engine.begin() as connection:
        existing = {
            str(row[0])
            for row in connection.execute(text("SHOW COLUMNS FROM lecture_briefings"))
        }
        for column, ddl in statements.items():
            if column not in existing:
                connection.execute(text(ddl))


def _now() -> datetime:
    return datetime.now()


def _clip(text: str, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _is_zh(lang: str) -> bool:
    return (lang or "").lower().startswith("zh")


def load_sentence_rows(db: Session, lecture_id: int, user_id: int) -> list[dict]:
    rows = (
        db.query(Transcription, Bookmark.tag)
        .outerjoin(
            Bookmark,
            (Bookmark.transcription_id == Transcription.id)
            & (Bookmark.user_id == user_id),
        )
        .filter(
            Transcription.lecture_id == lecture_id,
            Transcription.user_id == user_id,
        )
        .order_by(Transcription.sentence_order)
        .limit(BRIEFING_MAX_SENTENCES)
        .all()
    )
    sentences = []
    for transcription, tag in rows:
        sentences.append({
            "id": transcription.id,
            "sentence_order": transcription.sentence_order,
            "source_text": transcription.source_text or "",
            "translated_text": transcription.translated_text or "",
            "start_offset_ms": transcription.start_offset_ms or 0,
            "tag": tag,
        })
    return sentences


def _citation(sentence: dict, text: Optional[str] = None) -> dict:
    display = (text or sentence.get("translated_text") or sentence.get("source_text") or "").strip()
    return {
        "text": _clip(display, 240),
        "source_text": _clip(sentence.get("source_text") or "", 240),
        "sentence_order": int(sentence["sentence_order"]),
        "start_offset_ms": int(sentence.get("start_offset_ms") or 0),
        "tag": sentence.get("tag"),
    }


def _unique_by_order(items: list[dict], limit: int) -> list[dict]:
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


def _score_sentence(sentence: dict) -> int:
    tag = sentence.get("tag")
    source = f"{sentence.get('source_text', '')} {sentence.get('translated_text', '')}"
    score = 0
    if tag == "exam":
        score += 5
    elif tag == "important":
        score += 4
    elif tag == "definition":
        score += 3
    elif tag == "question":
        score += 2
    if _EXAM_PATTERN.search(source):
        score += 3
    text = sentence.get("translated_text") or sentence.get("source_text") or ""
    if len(text) >= 40:
        score += 1
    if "=" in source or "formula" in source.lower() or "公式" in source:
        score += 2
    return score


def _build_overview(course_name: str, duration_seconds: int,
                    sentences: list[dict], outline: list[dict],
                    target_lang: str) -> str:
    count = len(sentences)
    minutes = max(1, round((duration_seconds or 0) / 60)) if duration_seconds else 0
    first = next(
        (
            (item.get("translated_text") or item.get("source_text") or "").strip()
            for item in sentences if (item.get("translated_text") or item.get("source_text") or "").strip()
        ),
        "",
    )
    titles = "、".join(item["title"] for item in outline[:4]) if _is_zh(target_lang) else ", ".join(
        item["title"] for item in outline[:4]
    )
    if _is_zh(target_lang):
        parts = [f"本节《{course_name}》共 {count} 句"]
        if minutes:
            parts[0] += f"，约 {minutes} 分钟"
        parts[0] += "。"
        if first:
            parts.append(_clip(first, 120))
        if titles:
            parts.append(f"本课主要覆盖：{titles}。")
        return "".join(parts)
    parts = [f"{course_name}: {count} sentences"]
    if minutes:
        parts[0] += f", about {minutes} minutes"
    parts[0] += "."
    if first:
        parts.append(" " + _clip(first, 120))
    if titles:
        parts.append(f" Main sections: {titles}.")
    return "".join(parts)


def _build_outline(sentences: list[dict]) -> list[dict]:
    if not sentences:
        return []
    chunks: list[list[dict]] = []
    for index in range(0, len(sentences), _OUTLINE_CHUNK):
        chunks.append(sentences[index:index + _OUTLINE_CHUNK])
    if len(chunks) > 1 and len(chunks[-1]) < 3:
        chunks[-2].extend(chunks[-1])
        chunks.pop()
    outline = []
    for chunk in chunks:
        first = chunk[0]
        title_src = (first.get("translated_text") or first.get("source_text") or "").strip()
        outline.append({
            "title": _clip(title_src, 36) or f"#{first['sentence_order']}",
            "summary": _clip(title_src, 160),
            "start_order": first["sentence_order"],
            "end_order": chunk[-1]["sentence_order"],
            "start_offset_ms": first.get("start_offset_ms") or 0,
        })
    return outline


def _extract_term(sentence: dict) -> Optional[dict]:
    source = sentence.get("source_text") or ""
    translated = sentence.get("translated_text") or ""
    for text in (source, translated):
        for pattern in _TERM_PATTERNS:
            match = pattern.search(text.strip().rstrip("."))
            if not match:
                continue
            term = _clip(match.group(1).strip(" \"'“”"), 40)
            explanation = _clip((match.group(2) or translated or source).strip(" \"'“”"), 160)
            if term:
                return {
                    "term": term,
                    "explanation": explanation,
                    "source_text": _clip(source, 240),
                    "sentence_order": sentence["sentence_order"],
                    "start_offset_ms": sentence.get("start_offset_ms") or 0,
                }
    if sentence.get("tag") == "definition":
        return {
            "term": _clip(translated or source, 40),
            "explanation": _clip(translated or source, 160),
            "source_text": _clip(source, 240),
            "sentence_order": sentence["sentence_order"],
            "start_offset_ms": sentence.get("start_offset_ms") or 0,
        }
    return None


def _assignment(sentence: dict, text: Optional[str] = None) -> dict:
    """创建待确认的课堂行动项，不从语音文本臆测具体截止日期。"""
    display = (text or sentence.get("translated_text") or sentence.get("source_text") or "").strip()
    return {
        "text": _clip(display, 240),
        "source_text": _clip(sentence.get("source_text") or "", 240),
        "sentence_order": int(sentence["sentence_order"]),
        "start_offset_ms": int(sentence.get("start_offset_ms") or 0),
        "due_date": None,
        "needs_confirmation": True,
    }


def build_extractive_briefing(
    course_name: str,
    duration_seconds: int,
    sentences: list[dict],
    target_lang: str = "zh-CN",
) -> dict:
    """纯规则简报，便于单测，不访问数据库或外部 API。"""
    outline = _build_outline(sentences)
    ranked = sorted(sentences, key=_score_sentence, reverse=True)
    key_points = _unique_by_order(
        [_citation(item) for item in ranked if _score_sentence(item) >= 3],
        _MAX_KEY_POINTS,
    )
    if not key_points:
        key_points = _unique_by_order(
            [_citation(item) for item in ranked[:_MAX_KEY_POINTS]],
            _MAX_KEY_POINTS,
        )
    exam_hints = _unique_by_order(
        [
            _citation(item)
            for item in sentences
            if item.get("tag") == "exam"
            or _EXAM_PATTERN.search(f"{item.get('source_text', '')} {item.get('translated_text', '')}")
        ],
        _MAX_EXAM,
    )
    questions = _unique_by_order(
        [
            _citation(item)
            for item in sentences
            if item.get("tag") == "question"
            or _QUESTION_PATTERN.search(f"{item.get('source_text', '')} {item.get('translated_text', '')}")
        ],
        _MAX_QUESTIONS,
    )
    terms = []
    seen_terms = set()
    for item in sentences:
        extracted = _extract_term(item)
        if not extracted:
            continue
        key = extracted["term"].lower()
        if key in seen_terms:
            continue
        seen_terms.add(key)
        terms.append(extracted)
        if len(terms) >= _MAX_TERMS:
            break
    assignments = _unique_by_order(
        [
            _assignment(item)
            for item in sentences
            if _ASSIGNMENT_PATTERN.search(
                f"{item.get('source_text', '')} {item.get('translated_text', '')}"
            )
        ],
        _MAX_ASSIGNMENTS,
    )
    return {
        "overview": _build_overview(course_name, duration_seconds, sentences, outline, target_lang),
        "outline": outline,
        "key_points": key_points,
        "exam_hints": exam_hints,
        "questions": questions,
        "terms": terms,
        "assignments": assignments,
        "provider": "extractive",
    }


def _lookup_sentences(sentences: list[dict]) -> dict[int, dict]:
    return {int(item["sentence_order"]): item for item in sentences}


def _hydrate_citations(items: Any, lookup: dict[int, dict], limit: int) -> list[dict]:
    if not isinstance(items, list):
        return []
    result = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        try:
            order = int(raw.get("sentence_order"))
        except (TypeError, ValueError):
            continue
        sentence = lookup.get(order)
        if not sentence:
            continue
        text = raw.get("text") or sentence.get("translated_text") or sentence.get("source_text")
        result.append(_citation(sentence, str(text)))
        if len(result) >= limit:
            break
    return _unique_by_order(result, limit)


def _hydrate_outline(items: Any, lookup: dict[int, dict]) -> list[dict]:
    if not isinstance(items, list):
        return []
    outline = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        try:
            start_order = int(raw.get("start_order"))
            end_order = int(raw.get("end_order") or start_order)
        except (TypeError, ValueError):
            continue
        start = lookup.get(start_order)
        if not start or end_order < start_order:
            continue
        title = str(raw.get("title") or start.get("translated_text") or start.get("source_text") or "")
        summary = str(raw.get("summary") or title)
        outline.append({
            "title": _clip(title, 36),
            "summary": _clip(summary, 160),
            "start_order": start_order,
            "end_order": end_order,
            "start_offset_ms": start.get("start_offset_ms") or 0,
        })
    return outline


def _hydrate_terms(items: Any, lookup: dict[int, dict]) -> list[dict]:
    if not isinstance(items, list):
        return []
    terms = []
    seen = set()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        try:
            order = int(raw.get("sentence_order"))
        except (TypeError, ValueError):
            continue
        sentence = lookup.get(order)
        if not sentence:
            continue
        term = _clip(str(raw.get("term") or ""), 40)
        if not term or term.lower() in seen:
            continue
        seen.add(term.lower())
        terms.append({
            "term": term,
            "explanation": _clip(str(raw.get("explanation") or sentence.get("translated_text") or ""), 160),
            "source_text": _clip(sentence.get("source_text") or "", 240),
            "sentence_order": order,
            "start_offset_ms": sentence.get("start_offset_ms") or 0,
        })
        if len(terms) >= _MAX_TERMS:
            break
    return terms


def _hydrate_assignments(items: Any, lookup: dict[int, dict]) -> list[dict]:
    """只接受指向真实课堂句子的行动项，并强制标记为待用户确认。"""
    if not isinstance(items, list):
        return []
    assignments = []
    seen = set()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        try:
            order = int(raw.get("sentence_order"))
        except (TypeError, ValueError):
            continue
        if order in seen or order not in lookup:
            continue
        seen.add(order)
        assignments.append(_assignment(lookup[order], str(raw.get("text") or "")))
        if len(assignments) >= _MAX_ASSIGNMENTS:
            break
    return assignments


def merge_llm_briefing(extractive: dict, llm_payload: dict, sentences: list[dict]) -> dict:
    """用大模型结果覆盖文案，但只保留转录中真实存在的句子引用。"""
    lookup = _lookup_sentences(sentences)
    overview = str(llm_payload.get("overview") or "").strip()
    outline = _hydrate_outline(llm_payload.get("outline"), lookup)
    key_points = _hydrate_citations(llm_payload.get("key_points"), lookup, _MAX_KEY_POINTS)
    exam_hints = _hydrate_citations(llm_payload.get("exam_hints"), lookup, _MAX_EXAM)
    questions = _hydrate_citations(llm_payload.get("questions"), lookup, _MAX_QUESTIONS)
    terms = _hydrate_terms(llm_payload.get("terms"), lookup)
    assignments = _hydrate_assignments(llm_payload.get("assignments"), lookup)
    return {
        "overview": _clip(overview, 800) or extractive["overview"],
        "outline": outline or extractive["outline"],
        "key_points": key_points or extractive["key_points"],
        "exam_hints": exam_hints or extractive["exam_hints"],
        "questions": questions or extractive["questions"],
        "terms": terms or extractive["terms"],
        "assignments": assignments or extractive["assignments"],
        "provider": f"llm:{BRIEFING_LLM_MODEL}",
    }


def _parse_llm_json(raw: str) -> dict:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("简报模型未返回对象")
    return data


def _compact_sentences_for_llm(sentences: list[dict]) -> list[dict]:
    packed = []
    used = 0
    for item in sentences:
        row = {
            "order": item["sentence_order"],
            "src": _clip(item.get("source_text") or "", 180),
            "dst": _clip(item.get("translated_text") or "", 180),
        }
        if item.get("tag"):
            row["tag"] = item["tag"]
        encoded = json.dumps(row, ensure_ascii=False)
        if used + len(encoded) > _LLM_CHAR_BUDGET:
            break
        packed.append(row)
        used += len(encoded)
    return packed


def call_briefing_llm(course_name: str, target_lang: str, sentences: list[dict]) -> dict:
    if not (BRIEFING_LLM_API_URL and BRIEFING_LLM_API_KEY):
        raise RuntimeError("未配置课堂简报大模型")
    language = "简体中文" if _is_zh(target_lang) else target_lang
    payload_sentences = _compact_sentences_for_llm(sentences)
    user_prompt = (
        f"课程：{course_name}\n"
        f"简报语言：{language}\n"
        "根据课堂句子生成 JSON 简报，只能引用已有 order。\n"
        "字段：overview, outline[{title,start_order,end_order,summary}], "
        "key_points[{text,sentence_order}], exam_hints[{text,sentence_order}], "
        "questions[{text,sentence_order}], terms[{term,explanation,sentence_order}], "
        "assignments[{text,sentence_order}]\n"
        "句子：\n"
        + json.dumps(payload_sentences, ensure_ascii=False)
    )
    body = {
        "model": BRIEFING_LLM_MODEL,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是课堂简报助手。只根据给定句子归纳，不编造未出现的内容。"
                    "必须输出 JSON 对象。"
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
            last_error = RuntimeError(data.get("error", {}).get("message") if isinstance(data, dict) else response.status_code)
            continue
        try:
            content = data["choices"][0]["message"]["content"]
            usage = parse_usage_from_response(
                data,
                prompt_hint=user_prompt,
                completion_hint=content if isinstance(content, str) else "",
            )
            return _parse_llm_json(content), usage
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
    raise RuntimeError(f"课堂简报大模型不可用: {last_error}")


def _is_stale(row: LectureBriefing) -> bool:
    if row.status != "generating":
        return False
    stamp = row.updated_at or row.created_at
    if not stamp:
        return True
    return (_now() - stamp).total_seconds() > BRIEFING_STALE_SECONDS


def _empty_payload() -> dict:
    return {
        "overview": "",
        "outline": [],
        "key_points": [],
        "exam_hints": [],
        "questions": [],
        "terms": [],
        "assignments": [],
        "provider": "extractive",
    }


def _apply_payload(row: LectureBriefing, payload: dict, sentence_count: int,
                   status: str, error_message: Optional[str] = None) -> None:
    row.status = status
    row.provider = payload.get("provider")
    row.overview = payload.get("overview") or ""
    row.outline = payload.get("outline") or []
    row.key_points = payload.get("key_points") or []
    row.exam_hints = payload.get("exam_hints") or []
    row.questions = payload.get("questions") or []
    row.terms = payload.get("terms") or []
    row.assignments = payload.get("assignments") or []
    row.source_sentence_count = sentence_count
    row.error_message = error_message
    row.generated_at = _now() if status in {"ready", "empty"} else None
    row.edit_status = "auto"
    row.edited_at = None
    row.updated_at = _now()


def briefing_content_snapshot(row: LectureBriefing) -> dict:
    return {
        "overview": row.overview or "",
        "outline": row.outline or [],
        "key_points": row.key_points or [],
        "exam_hints": row.exam_hints or [],
        "questions": row.questions or [],
        "terms": row.terms or [],
        "assignments": row.assignments or [],
        "provider": row.provider,
        "source_sentence_count": row.source_sentence_count or 0,
        "edit_status": getattr(row, "edit_status", None) or "auto",
        "generated_at": row.generated_at.isoformat(sep=" ", timespec="seconds")
        if row.generated_at else None,
        "edited_at": row.edited_at.isoformat(sep=" ", timespec="seconds")
        if getattr(row, "edited_at", None) else None,
    }


def briefing_to_dict(row: LectureBriefing) -> dict:
    return {
        "lecture_id": row.lecture_id,
        "status": row.status,
        "edit_status": getattr(row, "edit_status", None) or "auto",
        "provider": row.provider,
        "overview": row.overview or "",
        "outline": row.outline or [],
        "key_points": row.key_points or [],
        "exam_hints": row.exam_hints or [],
        "questions": row.questions or [],
        "terms": row.terms or [],
        "assignments": row.assignments or [],
        "source_sentence_count": row.source_sentence_count or 0,
        "error_message": row.error_message,
        "generated_at": row.generated_at,
        "edited_at": getattr(row, "edited_at", None),
    }


def get_briefing(db: Session, lecture_id: int, user_id: int) -> Optional[LectureBriefing]:
    ensure_briefing_table()
    return db.query(LectureBriefing).filter(
        LectureBriefing.lecture_id == lecture_id,
        LectureBriefing.user_id == user_id,
    ).first()


def _sentence_lookup(db: Session, lecture_id: int, user_id: int) -> dict[int, dict]:
    return {
        int(row["sentence_order"]): row
        for row in load_sentence_rows(db, lecture_id, user_id)
    }


def _validate_order(order: int, lookup: dict[int, dict], *, field: str) -> None:
    if order <= 0:
        return
    if order not in lookup:
        raise ValueError(f"{field} 引用了不存在的句子 #{order}")


def _normalize_citation_items(items: list[dict], lookup: dict[int, dict],
                              *, field: str) -> list[dict]:
    normalized = []
    for item in items:
        order = int(item.get("sentence_order") or 0)
        _validate_order(order, lookup, field=field)
        text = _clip(str(item.get("text") or ""), 1000)
        if not text:
            continue
        start_ms = int(item.get("start_offset_ms") or 0)
        if order > 0:
            start_ms = int(lookup[order].get("start_offset_ms") or start_ms)
        source = str(item.get("source") or "auto").strip() or "auto"
        if source not in {"auto", "user_added", "from_attachment"}:
            source = "auto"
        attachment_id = item.get("attachment_id")
        try:
            attachment_id = int(attachment_id) if attachment_id else None
        except (TypeError, ValueError):
            attachment_id = None
        if attachment_id is not None and attachment_id <= 0:
            attachment_id = None
        normalized.append({
            "text": text,
            "source_text": _clip(str(item.get("source_text") or ""), 1000),
            "sentence_order": order,
            "start_offset_ms": max(0, start_ms),
            "tag": item.get("tag"),
            "source": source,
            "attachment_id": attachment_id,
        })
    return normalized


def _normalize_outline(items: list[dict], lookup: dict[int, dict]) -> list[dict]:
    normalized = []
    for item in items:
        start_order = int(item.get("start_order") or 0)
        end_order = int(item.get("end_order") or start_order)
        _validate_order(start_order, lookup, field="outline")
        _validate_order(end_order, lookup, field="outline")
        title = _clip(str(item.get("title") or ""), 200)
        if not title:
            continue
        start_ms = int(item.get("start_offset_ms") or 0)
        if start_order > 0:
            start_ms = int(lookup[start_order].get("start_offset_ms") or start_ms)
        normalized.append({
            "title": title,
            "summary": _clip(str(item.get("summary") or ""), 1000),
            "start_order": start_order,
            "end_order": end_order if end_order > 0 else start_order,
            "start_offset_ms": max(0, start_ms),
        })
    return normalized


def _normalize_terms(items: list[dict], lookup: dict[int, dict]) -> list[dict]:
    normalized = []
    for item in items:
        order = int(item.get("sentence_order") or 0)
        _validate_order(order, lookup, field="terms")
        term = _clip(str(item.get("term") or ""), 120)
        if not term:
            continue
        start_ms = int(item.get("start_offset_ms") or 0)
        if order > 0:
            start_ms = int(lookup[order].get("start_offset_ms") or start_ms)
        normalized.append({
            "term": term,
            "explanation": _clip(str(item.get("explanation") or ""), 1000),
            "source_text": _clip(str(item.get("source_text") or ""), 1000),
            "sentence_order": order,
            "start_offset_ms": max(0, start_ms),
        })
    return normalized


def _normalize_assignments(items: list[dict], lookup: dict[int, dict]) -> list[dict]:
    normalized = []
    for item in items:
        order = int(item.get("sentence_order") or 0)
        _validate_order(order, lookup, field="assignments")
        text = _clip(str(item.get("text") or ""), 1000)
        if not text:
            continue
        start_ms = int(item.get("start_offset_ms") or 0)
        if order > 0:
            start_ms = int(lookup[order].get("start_offset_ms") or start_ms)
        due = item.get("due_date")
        due_date = _clip(str(due), 64) if due else None
        source = str(item.get("source") or "auto").strip() or "auto"
        if source not in {"auto", "user_added", "from_attachment"}:
            source = "auto"
        attachment_id = item.get("attachment_id")
        try:
            attachment_id = int(attachment_id) if attachment_id else None
        except (TypeError, ValueError):
            attachment_id = None
        if attachment_id is not None and attachment_id <= 0:
            attachment_id = None
        normalized.append({
            "text": text,
            "source_text": _clip(str(item.get("source_text") or ""), 1000),
            "sentence_order": order,
            "start_offset_ms": max(0, start_ms),
            "due_date": due_date or None,
            "needs_confirmation": bool(item.get("needs_confirmation", True)),
            "source": source,
            "attachment_id": attachment_id,
        })
    return normalized


def patch_briefing(db: Session, lecture_id: int, user_id: int, updates: dict) -> LectureBriefing:
    """部分更新简报内容，标记为人工修订，并保留上一版快照便于单级回退。"""
    ensure_briefing_table()
    row = get_briefing(db, lecture_id, user_id)
    if not row:
        raise LookupError("简报不存在")
    if row.status == "generating":
        raise RuntimeError("简报生成中，暂不可编辑")
    if row.status not in {"ready", "empty", "failed"}:
        raise RuntimeError("当前简报状态不可编辑")

    lookup = _sentence_lookup(db, lecture_id, user_id)
    payload = briefing_content_snapshot(row)
    if "overview" in updates and updates["overview"] is not None:
        payload["overview"] = _clip(str(updates["overview"]), 4000)
    if "outline" in updates and updates["outline"] is not None:
        payload["outline"] = _normalize_outline(updates["outline"], lookup)
    if "key_points" in updates and updates["key_points"] is not None:
        payload["key_points"] = _normalize_citation_items(
            updates["key_points"], lookup, field="key_points"
        )
    if "exam_hints" in updates and updates["exam_hints"] is not None:
        payload["exam_hints"] = _normalize_citation_items(
            updates["exam_hints"], lookup, field="exam_hints"
        )
    if "questions" in updates and updates["questions"] is not None:
        payload["questions"] = _normalize_citation_items(
            updates["questions"], lookup, field="questions"
        )
    if "terms" in updates and updates["terms"] is not None:
        payload["terms"] = _normalize_terms(updates["terms"], lookup)
    if "assignments" in updates and updates["assignments"] is not None:
        payload["assignments"] = _normalize_assignments(updates["assignments"], lookup)

    row.previous_payload = briefing_content_snapshot(row)
    row.overview = payload["overview"]
    row.outline = payload["outline"]
    row.key_points = payload["key_points"]
    row.exam_hints = payload["exam_hints"]
    row.questions = payload["questions"]
    row.terms = payload["terms"]
    row.assignments = payload["assignments"]
    row.status = "ready"
    row.edit_status = "edited"
    row.edited_at = _now()
    row.error_message = None
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def confirm_briefing_assignment(db: Session, lecture_id: int, user_id: int,
                                index: int) -> LectureBriefing:
    ensure_briefing_table()
    row = get_briefing(db, lecture_id, user_id)
    if not row:
        raise LookupError("简报不存在")
    assignments = list(row.assignments or [])
    if index < 0 or index >= len(assignments):
        raise IndexError("作业项不存在")
    item = dict(assignments[index] or {})
    item["needs_confirmation"] = False
    assignments[index] = item
    row.previous_payload = briefing_content_snapshot(row)
    row.assignments = assignments
    row.edit_status = "edited"
    row.edited_at = _now()
    row.status = "ready"
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def delete_briefing_assignment(db: Session, lecture_id: int, user_id: int,
                               index: int) -> LectureBriefing:
    ensure_briefing_table()
    row = get_briefing(db, lecture_id, user_id)
    if not row:
        raise LookupError("简报不存在")
    assignments = list(row.assignments or [])
    if index < 0 or index >= len(assignments):
        raise IndexError("作业项不存在")
    row.previous_payload = briefing_content_snapshot(row)
    assignments.pop(index)
    row.assignments = assignments
    row.edit_status = "edited"
    row.edited_at = _now()
    row.status = "ready"
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def supplement_briefing_item(db: Session, lecture_id: int, user_id: int, *,
                             section: str, text: str, sentence_order: int = 0,
                             due_date: Optional[str] = None,
                             attachment_id: Optional[int] = None,
                             needs_confirmation: bool = False,
                             source: str = "user_added") -> LectureBriefing:
    """追加一条人工补充，并保证简报处于可编辑的 ready 状态。"""
    ensure_briefing_table()
    row = get_briefing(db, lecture_id, user_id)
    if not row:
        row = LectureBriefing(
            lecture_id=lecture_id, user_id=user_id, status="ready",
            overview="", outline=[], key_points=[], exam_hints=[],
            questions=[], terms=[], assignments=[], source_sentence_count=0,
            edit_status="edited",
        )
        db.add(row)
        db.flush()
    if row.status == "generating":
        raise RuntimeError("简报生成中，暂不可补充")

    lookup = _sentence_lookup(db, lecture_id, user_id)
    _validate_order(sentence_order, lookup, field=section)
    start_ms = 0
    if sentence_order > 0:
        start_ms = int(lookup[sentence_order].get("start_offset_ms") or 0)
    if source not in {"user_added", "from_attachment"}:
        source = "user_added"

    item = {
        "text": _clip(text, 1000),
        "source_text": "",
        "sentence_order": sentence_order,
        "start_offset_ms": start_ms,
        "source": source,
        "attachment_id": attachment_id,
    }
    if section == "assignments":
        item["due_date"] = _clip(due_date, 64) if due_date else None
        item["needs_confirmation"] = bool(needs_confirmation)
    elif section not in {"exam_hints", "key_points", "questions"}:
        raise ValueError("不支持的补充类型")

    row.previous_payload = briefing_content_snapshot(row)
    current = list(getattr(row, section) or [])
    current.append(item)
    setattr(row, section, current)
    row.status = "ready"
    row.edit_status = "edited"
    row.edited_at = _now()
    row.error_message = None
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def generate_briefing(db: Session, lecture_id: int, user_id: int,
                      force: bool = False) -> Optional[LectureBriefing]:
    """生成或返回已有简报。lecture 不存在时返回 None。"""
    ensure_briefing_table()
    lecture = db.query(Lecture).filter(
        Lecture.id == lecture_id, Lecture.user_id == user_id
    ).first()
    if not lecture:
        return None

    row = db.query(LectureBriefing).filter(
        LectureBriefing.lecture_id == lecture_id,
        LectureBriefing.user_id == user_id,
    ).with_for_update().first()
    if row and row.status == "generating" and not _is_stale(row) and not force:
        return row
    if row and row.status == "ready" and not force:
        return row

    if not row:
        row = LectureBriefing(
            lecture_id=lecture_id, user_id=user_id, status="generating",
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = db.query(LectureBriefing).filter(
                LectureBriefing.lecture_id == lecture_id,
                LectureBriefing.user_id == user_id,
            ).first()
            if not row:
                return None
            if row.status == "ready" and not force:
                return row
            if row.status == "generating" and not _is_stale(row) and not force:
                return row
            if force and (getattr(row, "edit_status", None) or "auto") == "edited":
                row.previous_payload = briefing_content_snapshot(row)
            row.status = "generating"
            row.error_message = None
            row.updated_at = _now()
            db.commit()
    else:
        if force and (getattr(row, "edit_status", None) or "auto") == "edited":
            row.previous_payload = briefing_content_snapshot(row)
        row.status = "generating"
        row.error_message = None
        row.updated_at = _now()
        db.commit()
    db.refresh(row)

    sentences = load_sentence_rows(db, lecture_id, user_id)
    if not sentences:
        _apply_payload(row, _empty_payload(), 0, "empty")
        db.commit()
        db.refresh(row)
        return row

    extractive = build_extractive_briefing(
        lecture.course_name, lecture.duration_seconds or 0, sentences, lecture.target_lang,
    )
    payload = extractive
    warning = None
    if BRIEFING_LLM_API_URL and BRIEFING_LLM_API_KEY:
        try:
            assert_within_quota(db, user_id)
            llm_payload, usage = call_briefing_llm(
                lecture.course_name, lecture.target_lang, sentences,
            )
            payload = merge_llm_briefing(extractive, llm_payload, sentences)
            record_usage(
                db,
                user_id=user_id,
                source="briefing",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                commit=False,
            )
        except QuotaExceededError as exc:
            logger.warning("课堂简报跳过 LLM（额度不足）: %s", exc)
            warning = str(exc)
        except Exception as exc:
            logger.warning("课堂简报大模型失败，回退抽取结果: %s", exc)
            warning = "大模型不可用，已使用抽取式简报"

    _apply_payload(row, payload, len(sentences), "ready", warning)
    db.commit()
    db.refresh(row)
    return row

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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import (BRIEFING_LLM_API_KEY, BRIEFING_LLM_API_URL,
                    BRIEFING_LLM_MODEL, BRIEFING_LLM_TIMEOUT_SECONDS,
                    BRIEFING_MAX_SENTENCES, BRIEFING_STALE_SECONDS)
from database import engine
from models.lecture import Bookmark, Lecture, LectureBriefing, Transcription


logger = logging.getLogger(__name__)

_TABLE_READY = False
_TABLE_LOCK = threading.Lock()
_OUTLINE_CHUNK = 8
_MAX_KEY_POINTS = 8
_MAX_EXAM = 6
_MAX_QUESTIONS = 6
_MAX_TERMS = 8
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
        _TABLE_READY = True


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
    return {
        "overview": _build_overview(course_name, duration_seconds, sentences, outline, target_lang),
        "outline": outline,
        "key_points": key_points,
        "exam_hints": exam_hints,
        "questions": questions,
        "terms": terms,
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


def merge_llm_briefing(extractive: dict, llm_payload: dict, sentences: list[dict]) -> dict:
    """用大模型结果覆盖文案，但只保留转录中真实存在的句子引用。"""
    lookup = _lookup_sentences(sentences)
    overview = str(llm_payload.get("overview") or "").strip()
    outline = _hydrate_outline(llm_payload.get("outline"), lookup)
    key_points = _hydrate_citations(llm_payload.get("key_points"), lookup, _MAX_KEY_POINTS)
    exam_hints = _hydrate_citations(llm_payload.get("exam_hints"), lookup, _MAX_EXAM)
    questions = _hydrate_citations(llm_payload.get("questions"), lookup, _MAX_QUESTIONS)
    terms = _hydrate_terms(llm_payload.get("terms"), lookup)
    return {
        "overview": _clip(overview, 800) or extractive["overview"],
        "outline": outline or extractive["outline"],
        "key_points": key_points or extractive["key_points"],
        "exam_hints": exam_hints or extractive["exam_hints"],
        "questions": questions or extractive["questions"],
        "terms": terms or extractive["terms"],
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
        "questions[{text,sentence_order}], terms[{term,explanation,sentence_order}]\n"
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
            return _parse_llm_json(content)
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
    row.source_sentence_count = sentence_count
    row.error_message = error_message
    row.generated_at = _now() if status in {"ready", "empty"} else None
    row.updated_at = _now()


def briefing_to_dict(row: LectureBriefing) -> dict:
    return {
        "lecture_id": row.lecture_id,
        "status": row.status,
        "provider": row.provider,
        "overview": row.overview or "",
        "outline": row.outline or [],
        "key_points": row.key_points or [],
        "exam_hints": row.exam_hints or [],
        "questions": row.questions or [],
        "terms": row.terms or [],
        "source_sentence_count": row.source_sentence_count or 0,
        "error_message": row.error_message,
        "generated_at": row.generated_at,
    }


def get_briefing(db: Session, lecture_id: int, user_id: int) -> Optional[LectureBriefing]:
    ensure_briefing_table()
    return db.query(LectureBriefing).filter(
        LectureBriefing.lecture_id == lecture_id,
        LectureBriefing.user_id == user_id,
    ).first()


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
            row.status = "generating"
            row.error_message = None
            row.updated_at = _now()
            db.commit()
    else:
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
            llm_payload = call_briefing_llm(
                lecture.course_name, lecture.target_lang, sentences,
            )
            payload = merge_llm_briefing(extractive, llm_payload, sentences)
        except Exception as exc:
            logger.warning("课堂简报大模型失败，回退抽取结果: %s", exc)
            warning = "大模型不可用，已使用抽取式简报"

    _apply_payload(row, payload, len(sentences), "ready", warning)
    db.commit()
    db.refresh(row)
    return row

"""LiveTrans Voice — 课后课堂助教问答。

优先检索本堂转录与收藏；配置 LLM 后可在标注【补充说明】的前提下适度补充。
未配置 LLM 时回退为检索模板回答。
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
from services.llm_quota import (QuotaExceededError, assert_within_quota,
                                parse_usage_from_response, record_usage)


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
_STOPWORDS = {
    "什么", "怎么", "怎样", "如何", "为什么", "是不是", "是否", "一下", "这个", "那个",
    "一个", "一些", "我们", "你们", "他们", "自己", "可以", "需要", "请问", "问问",
    "讲了", "讲的", "老师", "教授", "课程", "课堂", "这门", "这节", "本节", "内容",
    "问题", "解释", "说明", "告诉", "帮我", "关于", "如果", "因为", "所以", "但是",
    "然后", "以及", "还有", "或者", "的话", "吗", "呢", "啊", "吧", "了", "的", "是",
    "在", "有", "和", "与", "及", "等", "中", "上", "下", "为", "对", "从", "到",
    "么", "哪", "哪门", "哪些", "哪里", "多少", "几个",
    "what", "how", "why", "when", "where", "which", "the", "a", "an", "is", "are",
    "was", "were", "do", "does", "did", "can", "could", "please", "tell", "me",
}
_SUPPLEMENT_RULES = (
    "优先依据课堂证据回答；允许适度补充背景知识，但必须明确标注来源。"
    "课堂内容的每个事实性结论后附 [L课次IDS句子编号]，例如 [L12S3]。"
    "课外补充必须用【补充说明】……【/补充说明】包裹，并写明“以下不是课堂原文”。"
    "禁止把补充内容说成老师课上讲过。"
    "若课堂未直接提到，先说明“课堂记录未直接提到”，再给出标注过的补充。"
)


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
    """英文按词；中文按双字/短语切分，避免整句粘成一个 token 导致永远匹配不上。"""
    tokens: set[str] = set()
    for match in _TOKEN_RE.findall(text or ""):
        item = match.lower().strip()
        if not item or item in _STOPWORDS:
            continue
        if re.fullmatch(r"[a-z][a-z0-9_-]+", item):
            tokens.add(item)
            continue
        if len(item) == 1:
            continue
        for index in range(len(item) - 1):
            gram = item[index:index + 2]
            if gram not in _STOPWORDS:
                tokens.add(gram)
        if 2 <= len(item) <= 12:
            tokens.add(item)
    return tokens


def _citation(sentence: dict) -> dict:
    citation = {
        "sentence_order": int(sentence["sentence_order"]),
        "start_offset_ms": int(sentence.get("start_offset_ms") or 0),
        "source_text": sentence.get("source_text") or "",
        "translated_text": sentence.get("translated_text") or "",
        "tag": sentence.get("tag"),
    }
    # 跨课次检索时，编号只在单堂课内唯一；保留来源供前端跳转到正确回顾页。
    if sentence.get("lecture_id") is not None:
        citation["lecture_id"] = int(sentence["lecture_id"])
    if sentence.get("lecture_title"):
        citation["lecture_title"] = str(sentence["lecture_title"])
    if sentence.get("session_number") is not None:
        citation["session_number"] = int(sentence["session_number"])
    return citation


def _unique_hits(items: list[dict], limit: int = _MAX_HITS) -> list[dict]:
    seen = set()
    result = []
    for item in items:
        order = item.get("sentence_order")
        identity = (item.get("lecture_id"), order)
        if identity in seen:
            continue
        seen.add(identity)
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
    prefix = f"#{order}"
    if sentence.get("session_number") is not None:
        prefix = f"第{sentence['session_number']}节 {prefix}"
    translated = (sentence.get("translated_text") or "").strip()
    source = (sentence.get("source_text") or "").strip()
    if quote:
        return f"{prefix} 原文：{source}\n译文：{translated}"
    return f"{prefix} {translated or source}"


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
            "answer": (
                "课堂记录里没有直接匹配到相关句子。"
                "你可以换个更具体的关键词再问；也可以问“这节课讲了什么”先看整体脉络。"
            ),
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
        "若需补充背景，把补充放进 answer，并用【补充说明】……【/补充说明】标注，且不要写进 citation_orders。"
        "输出 JSON：{\"answer\":\"...\",\"citation_orders\":[3,7]}"
    )
    body = {
        "model": BRIEFING_LLM_MODEL,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是课堂助教。" + _SUPPLEMENT_RULES +
                    "必须输出 JSON。"
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
            usage = parse_usage_from_response(
                data,
                prompt_hint=user_prompt,
                completion_hint=content if isinstance(content, str) else "",
            )
            return _parse_llm_json(content), usage
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
    assert_within_quota(db, user_id)
    try:
        llm_payload, usage = _call_assistant_llm(
            question, course_name, briefing.get("overview") or "", hits, history or [],
        )
        merged = merge_llm_answer(template, llm_payload, hits)
        record_usage(
            db,
            user_id=user_id,
            source="assistant",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )
        merged["used_briefing"] = template["used_briefing"]
        return merged
    except QuotaExceededError:
        raise
    except Exception as exc:
        logger.warning("课堂助教大模型失败，回退模板回答: %s", exc)
        return template


def _call_scope_assistant_llm(question: str, scope_name: str, summary: str,
                              hits: list[dict], history: list[dict]) -> dict:
    """课程级问答的受限模型调用，引用键同时包含课堂和句子编号。"""
    evidence = []
    for item in hits:
        reference = f"L{item.get('lecture_id', 0)}S{item['sentence_order']}"
        evidence.append({
            "ref": reference,
            "lecture": item.get("lecture_title") or "课堂记录",
            "session": item.get("session_number"),
            "src": item.get("source_text") or "",
            "dst": item.get("translated_text") or "",
            "tag": item.get("tag"),
        })
    compact_history = []
    for item in (history or [])[-_MAX_HISTORY:]:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            compact_history.append({"role": role, "content": content[:400]})
    user_prompt = (
        f"查询范围：{scope_name}\n"
        f"较早会话摘要：{summary or '（无）'}\n"
        f"最近对话：{json.dumps(compact_history, ensure_ascii=False)}\n"
        f"课堂证据：{json.dumps(evidence, ensure_ascii=False)}\n"
        f"学生问题：{question}\n"
        + _SUPPLEMENT_RULES
        + "输出 JSON：{\"answer\":\"...\",\"citation_refs\":[\"L12S3\"]}。"
    )
    body = {
        "model": BRIEFING_LLM_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "你是严谨的课堂学习助手。" + _SUPPLEMENT_RULES + "必须输出 JSON。"},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Accept": "application/json", "Content-Type": "application/json",
        "Authorization": f"Bearer {BRIEFING_LLM_API_KEY}", "User-Agent": "LiveTrans/1.4",
    }
    last_error = None
    for use_json_format in (True, False):
        request_body = dict(body)
        if use_json_format:
            request_body["response_format"] = {"type": "json_object"}
        try:
            response = requests.post(BRIEFING_LLM_API_URL, json=request_body, headers=headers,
                                     timeout=BRIEFING_LLM_TIMEOUT_SECONDS)
            data = response.json()
            if not response.ok:
                raise RuntimeError(str(data)[:200])
            content = data["choices"][0]["message"]["content"]
            usage = parse_usage_from_response(
                data,
                prompt_hint=user_prompt,
                completion_hint=content if isinstance(content, str) else "",
            )
            return _parse_llm_json(content), usage
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError, RuntimeError) as exc:
            last_error = exc
    raise RuntimeError(f"课程助教大模型不可用: {last_error}")


def _iter_text_chunks(text: str, size: int = 18):
    """把完整回答切成小段，便于无 LLM 时也有可见的流式效果。"""
    content = text or ""
    if not content:
        return
    index = 0
    length = len(content)
    while index < length:
        end = min(index + size, length)
        if end < length:
            # 尽量在标点或换行处断开，避免把词切得太碎。
            window = content[index:min(end + 8, length)]
            break_at = -1
            for marker in ("\n", "。", "！", "？", "；", "，", ".", "!", "?", ";", ",", " "):
                pos = window.rfind(marker)
                if pos >= max(0, size // 3):
                    break_at = max(break_at, pos)
            if break_at >= 0:
                end = index + break_at + 1
        yield content[index:end]
        index = end


def _stream_text_as_deltas(text: str):
    for chunk in _iter_text_chunks(text):
        yield {"type": "delta", "content": chunk}


def _stream_scope_assistant_llm(question: str, scope_name: str, summary: str,
                                hits: list[dict], history: list[dict]):
    """以 OpenAI-compatible SSE 格式产出课程回答的文本增量。"""
    evidence = []
    for item in hits:
        reference = f"L{item.get('lecture_id', 0)}S{item['sentence_order']}"
        evidence.append({
            "ref": reference,
            "lecture": item.get("lecture_title") or "课堂记录",
            "session": item.get("session_number"),
            "src": item.get("source_text") or "",
            "dst": item.get("translated_text") or "",
            "tag": item.get("tag"),
        })
    compact_history = []
    for item in (history or [])[-_MAX_HISTORY:]:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            compact_history.append({"role": role, "content": content[:400]})
    user_prompt = (
        f"查询范围：{scope_name}\n"
        f"较早会话摘要：{summary or '（无）'}\n"
        f"最近对话：{json.dumps(compact_history, ensure_ascii=False)}\n"
        f"课堂证据：{json.dumps(evidence, ensure_ascii=False)}\n"
        f"学生问题：{question}\n"
        + _SUPPLEMENT_RULES
        + "不要输出 JSON、Markdown 代码块或单独的引用列表。"
    )
    body = {
        "model": BRIEFING_LLM_MODEL,
        "temperature": 0.2,
        "stream": True,
        "messages": [
            {"role": "system", "content": "你是严谨的课堂学习助手。" + _SUPPLEMENT_RULES},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BRIEFING_LLM_API_KEY}",
        "User-Agent": "LiveTrans/1.4",
    }
    # connect / read 分离：流式回答可能在整段超时前持续推送。
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
        # 强制按 UTF-8 解码：上游若未声明 charset，requests 默认 ISO-8859-1 会把中文弄成乱码。
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


def _merge_scope_stream_answer(template: dict, answer: str, hits: list[dict]) -> dict:
    """保留模型回答；课堂引用只接受本次检索命中，补充段落靠【补充说明】标注。"""
    lookup = {f"L{item.get('lecture_id', 0)}S{item['sentence_order']}": item for item in hits}
    refs = re.findall(r"\[?(L\d+S\d+)\]?", answer or "")
    selected = []
    for ref in refs:
        item = lookup.get(ref)
        if item is not None and item not in selected:
            selected.append(item)
    clean_answer = (answer or "").strip()
    if not clean_answer:
        return template
    has_supplement = "【补充说明】" in clean_answer
    if not selected and hits and not has_supplement:
        selected = hits[: min(3, len(hits))]
    return {
        "answer": clean_answer,
        "citations": [_citation(item) for item in selected],
        "provider": f"llm:{BRIEFING_LLM_MODEL}",
        "used_briefing": False,
    }


def stream_scope_question(db, lecture_ids: list[int], user_id: int, question: str,
                          *, scope_name: str = "课堂记录", history: Optional[list[dict]] = None,
                          summary: str = "", hint: Optional[str] = None,
                          assignment_id: Optional[str] = None,
                          image_ocr: Optional[str] = None):
    """产出 tool_* / ``delta`` / ``done``；经工具取证后再回答，避免全文上送。"""
    from models.lecture import Lecture
    from services.tools.agent import stream_with_tools

    lectures = db.query(Lecture).filter(
        Lecture.status == "completed",
        Lecture.id.in_(lecture_ids),
    ).order_by(Lecture.lecture_date.asc(), Lecture.started_at.asc(), Lecture.id.asc()).all()
    # 只保留已授权集合内的课次（由路由层先做可读性校验后再传入 ID）。
    allowed = {int(value) for value in lecture_ids}
    lectures = [row for row in lectures if int(row.id) in allowed]
    if not lectures:
        empty = {
            "answer": "所选范围内还没有可用的课堂转录，暂时无法回答。",
            "citations": [], "provider": "extractive", "used_briefing": False,
            "tools_used": [],
        }
        yield from _stream_text_as_deltas(empty["answer"])
        yield {"type": "done", "result": empty}
        return

    yield from stream_with_tools(
        db, lectures, user_id, question,
        scope_name=scope_name, history=history or [], summary=summary or "",
        hint=hint, assignment_id=assignment_id, image_ocr=image_ocr,
    )


def _merge_scope_llm_answer(template: dict, payload: dict, hits: list[dict]) -> dict:
    lookup = {f"L{item.get('lecture_id', 0)}S{item['sentence_order']}": item for item in hits}
    refs = payload.get("citation_refs") or []
    selected = []
    if isinstance(refs, list):
        for ref in refs:
            item = lookup.get(str(ref))
            if item is not None and item not in selected:
                selected.append(item)
    answer = str(payload.get("answer") or "").strip()
    if not answer:
        return template
    has_supplement = "【补充说明】" in answer
    if not selected and not has_supplement:
        return template
    return {
        "answer": answer,
        "citations": [_citation(item) for item in selected],
        "provider": f"llm:{BRIEFING_LLM_MODEL}",
        "used_briefing": False,
    }


def answer_scope_question(db, lectures: list, user_id: int, question: str,
                          *, scope_name: str = "课堂记录", history: Optional[list[dict]] = None,
                          summary: str = "") -> dict:
    """面向独立学习助手的课程级检索。

    原文始终留在数据库中：这里只读取已授权课堂、按问题挑选最多十句证据，
    不会把整门课程或完整会话发送给模型。向量索引上线前使用这一可靠的关键词
    基线，且每条证据仍保留课次和时间戳。
    """
    sentences: list[dict] = []
    for lecture in lectures:
        rows = load_sentence_rows(db, lecture.id, int(lecture.user_id))
        lecture_title = getattr(lecture, "title", None) or getattr(lecture, "course_name", "课堂记录")
        for row in rows:
            row["lecture_id"] = lecture.id
            row["lecture_title"] = lecture_title
            row["session_number"] = getattr(lecture, "session_number", None)
            sentences.append(row)
    if not sentences:
        return {
            "answer": "所选范围内还没有可用的课堂转录，暂时无法回答。",
            "citations": [],
            "provider": "extractive",
            "used_briefing": False,
        }
    intent, hits = retrieve_sentences(question, sentences, {})
    result = build_template_answer(question, intent, hits, {})
    result["used_briefing"] = False
    if not (BRIEFING_LLM_API_URL and BRIEFING_LLM_API_KEY):
        return result
    assert_within_quota(db, user_id)
    try:
        payload, usage = _call_scope_assistant_llm(question, scope_name, summary, hits, history or [])
        record_usage(
            db,
            user_id=user_id,
            source="assistant",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )
        return _merge_scope_llm_answer(result, payload, hits)
    except QuotaExceededError:
        raise
    except Exception as exc:
        logger.warning("课程学习助手大模型失败，回退检索回答: %s", exc)
        return result

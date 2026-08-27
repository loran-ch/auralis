"""实时字幕切分与预览裁剪，避免单条无限变长。"""
from __future__ import annotations

import re
from typing import Optional


_STRONG_PUNCT = set("。！？；.!?;\n")
_WEAK_PUNCT = set("，、,;:： ")
_INCOMPLETE_ENDINGS = (
    "当中", "包括", "以及", "或者", "因为", "所以", "但是", "而且", "就是",
    "一个", "一种", "一些", "这个", "那个", "我们", "他们", "进行", "通过",
    "首先", "其次", "然后", "例如", "比如", "关于", "对于", "根据",
)


def looks_incomplete(text: str, min_chars: int) -> bool:
    """短句或语义未收束时，倾向继续合并下一段。"""
    value = (text or "").strip()
    if not value:
        return True
    if len(value) < min_chars:
        return True
    bare = value.rstrip("。！？.!?;；…")
    for ending in _INCOMPLETE_ENDINGS:
        if bare.endswith(ending):
            return True
    # 以逗号类弱标点收尾，通常还没讲完。
    if value[-1] in _WEAK_PUNCT:
        return True
    return False


def join_segment_parts(parts: list[str]) -> str:
    cleaned = [re.sub(r"\s+", " ", (part or "").strip()) for part in parts if (part or "").strip()]
    if not cleaned:
        return ""
    # 中文片段直接拼接；英文之间补空格。
    out = cleaned[0]
    for part in cleaned[1:]:
        if out and part and (out[-1].isascii() and out[-1].isalnum()) and (
            part[0].isascii() and part[0].isalnum()
        ):
            out += " " + part
        else:
            out += part
    return out


def preview_translate_tail(text: str, max_chars: int) -> str:
    """interim 预览翻译只取尾部，控制翻译成本。"""
    value = (text or "").strip()
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    return value[-max_chars:]


def display_preview_text(text: str, max_chars: int) -> str:
    """界面可显示带省略的原文预览。"""
    value = (text or "").strip()
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    return "…" + value[-(max_chars - 1):]


def uncommitted_suffix(text: str, committed_prefix: str) -> tuple[str, str]:
    """返回 (未提交后缀, 更新后的 committed_prefix)。

    ASR 通常整句替换增长；若已强制落库前缀，后续只处理增量。
    """
    full = (text or "").strip()
    prefix = committed_prefix or ""
    if not full:
        return "", prefix
    if prefix and full.startswith(prefix):
        return full[len(prefix):].lstrip(), prefix
    # 上游换了新句子或改写，丢弃旧前缀。
    return full, ""


def split_transcript_segments(text: str, max_chars: int) -> list[str]:
    """把过长原文切成多条，优先在强标点处断开。"""
    value = re.sub(r"\s+", " ", (text or "").strip())
    if not value:
        return []
    if max_chars <= 0 or len(value) <= max_chars:
        return [value]

    segments: list[str] = []
    start = 0
    length = len(value)
    while start < length:
        if length - start <= max_chars:
            piece = value[start:].strip()
            if piece:
                segments.append(piece)
            break
        window_end = start + max_chars
        cut = _best_cut(value, start, window_end)
        piece = value[start:cut].strip()
        if not piece:
            # 保底硬切，避免死循环。
            cut = window_end
            piece = value[start:cut].strip()
        if piece:
            segments.append(piece)
        start = cut
        while start < length and value[start].isspace():
            start += 1
    return segments


def _best_cut(text: str, start: int, window_end: int) -> int:
    strong = -1
    weak = -1
    # 至少保留一点前缀，避免切在开头。
    min_pos = start + max(8, (window_end - start) // 5)
    for index in range(window_end - 1, min_pos - 1, -1):
        ch = text[index]
        if ch in _STRONG_PUNCT:
            strong = index + 1
            break
        if weak < 0 and ch in _WEAK_PUNCT:
            weak = index + 1
    if strong > start:
        return strong
    if weak > start:
        return weak
    return window_end


def should_force_finalize(
    active_text: str,
    *,
    max_chars: int,
    open_since: Optional[float],
    now: float,
    force_ms: int,
    min_chars: int = 12,
) -> bool:
    active = (active_text or "").strip()
    if not active:
        return False
    if max_chars > 0 and len(active) >= max_chars:
        return True
    if force_ms > 0 and open_since is not None and len(active) >= min_chars:
        if (now - open_since) * 1000 >= force_ms:
            return True
    return False


def distribute_offsets(
    start_offset_ms: int,
    end_offset_ms: int,
    chunk_count: int,
) -> list[tuple[int, int]]:
    if chunk_count <= 0:
        return []
    start = max(0, int(start_offset_ms or 0))
    end = max(start, int(end_offset_ms or start))
    if chunk_count == 1:
        return [(start, end)]
    span = max(chunk_count, end - start)
    step = max(1, span // chunk_count)
    ranges = []
    cursor = start
    for index in range(chunk_count):
        chunk_end = end if index == chunk_count - 1 else cursor + step
        ranges.append((cursor, max(cursor, chunk_end)))
        cursor = chunk_end
    return ranges

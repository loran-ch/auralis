"""课堂简报 Markdown 导出与资料 ZIP 打包。"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from sqlalchemy.orm import Session

from services.attachments import list_attachments
from services.briefing import briefing_to_dict, get_briefing


_ATTACHMENT_ROOT = (
    Path(__file__).resolve().parent.parent.parent / "frontend" / "uploads" / "attachments"
)


def _safe_filename(name: str, fallback: str = "file") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\r\n]+", "_", (name or "").strip())
    cleaned = cleaned.strip(" .") or fallback
    return cleaned[:120]


def _line_items(title: str, items: list, *, text_key: str = "text") -> list[str]:
    if not items:
        return []
    lines = [f"## {title}", ""]
    for index, item in enumerate(items, start=1):
        text = (item.get(text_key) or item.get("term") or "").strip()
        order = item.get("sentence_order")
        suffix = f" （#{order}）" if order else ""
        if item.get("term") and item.get("explanation"):
            text = f"{item.get('term')}：{item.get('explanation')}"
        lines.append(f"{index}. {text}{suffix}")
    lines.append("")
    return lines


def briefing_to_markdown(lecture, briefing: Optional[dict]) -> str:
    title = (
        getattr(lecture, "title", None)
        or (
            f"{getattr(lecture, 'course_name', '课堂')} · 第 {lecture.session_number} 节课"
            if getattr(lecture, "session_number", None)
            else getattr(lecture, "course_name", None)
        )
        or f"课堂 {lecture.id}"
    )
    lines = [f"# {title}", ""]
    if getattr(lecture, "lecture_date", None):
        lines.append(f"- 上课日期：{lecture.lecture_date}")
    if getattr(lecture, "duration_seconds", None):
        minutes = int(lecture.duration_seconds or 0) // 60
        lines.append(f"- 时长：约 {minutes} 分钟")
    if getattr(lecture, "audio_url", None):
        lines.append(f"- 录音：{lecture.audio_url}")
    lines.append("")

    if not briefing or briefing.get("status") not in {"ready", "empty"}:
        lines.extend(["## 简报", "", "暂无可用简报。", ""])
        return "\n".join(lines).strip() + "\n"

    overview = (briefing.get("overview") or "").strip()
    lines.extend(["## 概述", "", overview or "（无）", ""])

    outline = briefing.get("outline") or []
    if outline:
        lines.extend(["## 提纲", ""])
        for item in outline:
            title_text = (item.get("title") or item.get("text") or "").strip()
            start = item.get("start_order")
            suffix = f" （起 #{start}）" if start else ""
            lines.append(f"- {title_text}{suffix}")
        lines.append("")

    lines.extend(_line_items("要点", briefing.get("key_points") or []))
    lines.extend(_line_items("考点", briefing.get("exam_hints") or []))
    lines.extend(_line_items("作业与通知", briefing.get("assignments") or []))
    lines.extend(_line_items("疑问", briefing.get("questions") or []))
    lines.extend(_line_items("术语", briefing.get("terms") or [], text_key="term"))
    return "\n".join(lines).strip() + "\n"


def build_briefing_markdown(db: Session, lecture, user_id: int) -> str:
    row = get_briefing(db, lecture.id, user_id)
    data = briefing_to_dict(row) if row else None
    return briefing_to_markdown(lecture, data)


def content_disposition(filename: str) -> str:
    ascii_name = re.sub(r"[^\x20-\x7E]", "_", filename) or "download"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


def local_attachment_path(url: Optional[str]) -> Optional[Path]:
    if not url or not url.startswith("/uploads/attachments/"):
        return None
    name = Path(url).name
    path = (_ATTACHMENT_ROOT / name).resolve()
    try:
        path.relative_to(_ATTACHMENT_ROOT.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def build_materials_zip(db: Session, lecture, user_id: int) -> bytes:
    markdown = build_briefing_markdown(db, lecture, user_id)
    attachments = list_attachments(db, lecture.id, user_id)
    buffer = io.BytesIO()
    used_names = set()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("briefing.md", markdown.encode("utf-8"))
        readme = [
            "# 资料包说明",
            "",
            "- `briefing.md`：课堂简报导出",
            "- `attachments/`：本节上传的学习资料（含课件 PPT/PDF 等）",
            "",
        ]
        if getattr(lecture, "audio_url", None):
            readme.append(f"- 课堂录音地址：`{lecture.audio_url}`")
            readme.append("")
        archive.writestr("README.md", "\n".join(readme).encode("utf-8"))
        if attachments:
            for index, row in enumerate(attachments, start=1):
                path = local_attachment_path(row.url)
                if not path:
                    continue
                ext = path.suffix or ""
                base = _safe_filename(row.title or f"attachment-{index}", f"attachment-{index}")
                if not base.lower().endswith(ext.lower()):
                    base = f"{base}{ext}"
                candidate = base
                n = 2
                while candidate.lower() in used_names:
                    stem = Path(base).stem
                    candidate = f"{stem}-{n}{ext}"
                    n += 1
                used_names.add(candidate.lower())
                archive.write(path, arcname=f"attachments/{candidate}")
    return buffer.getvalue()

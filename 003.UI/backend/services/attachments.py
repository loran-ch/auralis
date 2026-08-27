"""课堂人工附件：作业截图、考点板书、通知 PDF、课件 PPT。"""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from database import engine
from models.lecture import LectureAttachment


_TABLE_READY = False
_TABLE_LOCK = threading.Lock()

ATTACHMENT_CATEGORIES = {"assignment", "exam", "notice", "other", "material"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
}
MATERIAL_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def ensure_attachment_table() -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return
    with _TABLE_LOCK:
        if _TABLE_READY:
            return
        LectureAttachment.__table__.create(bind=engine, checkfirst=True)
        # 兼容已建库：补齐 material 枚举值。
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE lecture_attachments MODIFY COLUMN category "
                    "ENUM('assignment','exam','notice','other','material') "
                    "NOT NULL DEFAULT 'other'"
                ))
        except Exception:
            pass
        _TABLE_READY = True


def attachment_to_dict(row: LectureAttachment) -> dict:
    return {
        "id": row.id,
        "lecture_id": row.lecture_id,
        "category": row.category,
        "title": row.title,
        "url": row.url,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "status": row.status,
        "error_message": row.error_message,
        "created_at": row.created_at,
    }


def list_attachments(db: Session, lecture_id: int, user_id: int,
                     category: Optional[str] = None) -> list[LectureAttachment]:
    ensure_attachment_table()
    query = db.query(LectureAttachment).filter(
        LectureAttachment.lecture_id == lecture_id,
        LectureAttachment.user_id == user_id,
    )
    if category:
        query = query.filter(LectureAttachment.category == category)
    return query.order_by(LectureAttachment.created_at.desc(), LectureAttachment.id.desc()).all()


def get_attachment(db: Session, lecture_id: int, user_id: int,
                   attachment_id: int) -> Optional[LectureAttachment]:
    ensure_attachment_table()
    return db.query(LectureAttachment).filter(
        LectureAttachment.id == attachment_id,
        LectureAttachment.lecture_id == lecture_id,
        LectureAttachment.user_id == user_id,
    ).first()


def create_attachment(db: Session, *, lecture_id: int, user_id: int, category: str,
                      title: str, url: str, content_type: Optional[str],
                      size_bytes: Optional[int]) -> LectureAttachment:
    ensure_attachment_table()
    if category not in ATTACHMENT_CATEGORIES:
        raise ValueError("不支持的附件类别")
    row = LectureAttachment(
        lecture_id=lecture_id,
        user_id=user_id,
        category=category,
        title=(title or "课堂附件").strip()[:256] or "课堂附件",
        url=url,
        content_type=content_type,
        size_bytes=size_bytes,
        status="ready",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_attachment(db: Session, lecture_id: int, user_id: int,
                      attachment_id: int) -> Optional[str]:
    """删除附件记录，返回本地 URL 供调用方清理文件。"""
    ensure_attachment_table()
    row = get_attachment(db, lecture_id, user_id, attachment_id)
    if not row:
        return None
    url = row.url
    db.delete(row)
    db.commit()
    return url


def extension_for_upload(content_type: Optional[str], header: bytes,
                         filename: Optional[str] = None) -> Optional[str]:
    if content_type in ALLOWED_CONTENT_TYPES:
        return ALLOWED_CONTENT_TYPES[content_type]
    if header.startswith(b"%PDF"):
        return ".pdf"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP":
        return ".webp"
    # PPTX 是 ZIP 容器；PPT 是 OLE 复合文档。结合文件名兜底，避免浏览器 MIME 缺失。
    name = (filename or "").lower()
    if name.endswith(".pptx") and header[:2] == b"PK":
        return ".pptx"
    if name.endswith(".ppt") and header[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return ".ppt"
    if header[:2] == b"PK" and content_type in {
        "application/zip",
        "application/octet-stream",
        "",
        None,
    } and name.endswith(".pptx"):
        return ".pptx"
    return None


def max_upload_mb_for(category: str, content_type: Optional[str], ext: Optional[str]) -> int:
    from config import MAX_ATTACHMENT_SIZE_MB, MAX_MATERIAL_SIZE_MB

    if category == "material" or (content_type in MATERIAL_CONTENT_TYPES) or (ext in {".ppt", ".pptx"}):
        return MAX_MATERIAL_SIZE_MB
    return MAX_ATTACHMENT_SIZE_MB

"""LiveTrans Voice — 知识卡片(收藏)服务"""
from typing import Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from models.lecture import Bookmark, Lecture, Transcription


def add_bookmark(db: Session, user_id: int, transcription_id: int,
                 tag: str, note: Optional[str] = None) -> Optional[dict]:
    """收藏一条转录句子"""
    transcription = db.query(Transcription).filter(
        Transcription.id == transcription_id,
        Transcription.user_id == user_id,
    ).first()
    if not transcription:
        return None

    # 检查是否已收藏
    existing = db.query(Bookmark).filter(
        Bookmark.user_id == user_id,
        Bookmark.transcription_id == transcription_id,
    ).first()
    if existing:
        existing.tag = tag
        existing.note = note.strip() or None if note is not None else existing.note
        db.commit()
        return {
            "bookmark_id": existing.id,
            "tag": existing.tag,
            "source_text": transcription.source_text,
            "translated_text": transcription.translated_text,
            "note": existing.note,
        }

    bookmark = Bookmark(
        user_id=user_id, transcription_id=transcription_id,
        lecture_id=transcription.lecture_id, tag=tag,
        note=note.strip() or None if note else None,
    )
    db.add(bookmark)
    try:
        db.flush()
    except IntegrityError:
        # 数据库唯一约束处理并发重复点击；回查后返回幂等结果。
        db.rollback()
        transcription = db.query(Transcription).filter(
            Transcription.id == transcription_id,
            Transcription.user_id == user_id,
        ).first()
        existing = db.query(Bookmark).filter(
            Bookmark.user_id == user_id,
            Bookmark.transcription_id == transcription_id,
        ).first()
        if not transcription or not existing:
            return None
        return {
            "bookmark_id": existing.id,
            "tag": existing.tag,
            "source_text": transcription.source_text,
            "translated_text": transcription.translated_text,
            "note": existing.note,
        }

    # 更新 transcription 的收藏标记
    transcription.is_bookmarked = True
    lecture = db.query(Lecture).filter(Lecture.id == transcription.lecture_id).first()
    if lecture:
        lecture.bookmark_count = (lecture.bookmark_count or 0) + 1
    db.commit()
    db.refresh(bookmark)

    return {
        "bookmark_id": bookmark.id,
        "tag": bookmark.tag,
        "source_text": transcription.source_text,
        "translated_text": transcription.translated_text,
        "note": bookmark.note,
    }


def remove_bookmark(db: Session, user_id: int, bookmark_id: int) -> bool:
    """取消收藏"""
    bookmark = db.query(Bookmark).filter(
        Bookmark.id == bookmark_id, Bookmark.user_id == user_id
    ).first()
    if not bookmark:
        return False

    # 更新 transcription 标记
    db.query(Transcription).filter(
        Transcription.id == bookmark.transcription_id
    ).update({"is_bookmarked": False})
    lecture = db.query(Lecture).filter(Lecture.id == bookmark.lecture_id).first()
    if lecture:
        lecture.bookmark_count = max(0, (lecture.bookmark_count or 0) - 1)

    db.delete(bookmark)
    db.commit()
    return True


def get_bookmarks(db: Session, user_id: int, tag: Optional[str] = None,
                  limit: int = 50) -> list:
    """获取用户收藏列表，支持按标签筛选"""
    q = db.query(Bookmark).filter(Bookmark.user_id == user_id)
    if tag:
        q = q.filter(Bookmark.tag == tag)
    return q.order_by(Bookmark.created_at.desc()).limit(limit).all()

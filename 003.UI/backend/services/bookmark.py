"""LiveTrans Voice — 知识卡片(收藏)服务"""
from typing import Optional
from sqlalchemy.orm import Session
from models.lecture import Transcription
from models.lecture import Bookmark


def add_bookmark(db: Session, user_id: int, transcription_id: int,
                 tag: str) -> Optional[dict]:
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
        return {"message": "已收藏", "bookmark_id": existing.id, "tag": existing.tag}

    bookmark = Bookmark(
        user_id=user_id, transcription_id=transcription_id,
        lecture_id=transcription.lecture_id, tag=tag,
    )
    db.add(bookmark)

    # 更新 transcription 的收藏标记
    transcription.is_bookmarked = True
    db.commit()
    db.refresh(bookmark)

    return {
        "bookmark_id": bookmark.id,
        "tag": bookmark.tag,
        "source_text": transcription.source_text,
        "translated_text": transcription.translated_text,
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

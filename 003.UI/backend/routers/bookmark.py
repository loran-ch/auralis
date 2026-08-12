"""LiveTrans Voice — 知识卡片(收藏)路由"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.lecture import Bookmark, Transcription, Lecture
from routers.auth import get_current_user
from services.bookmark import add_bookmark, remove_bookmark, get_bookmarks
from schemas.lecture import (BookmarkListItem, BookmarkReq, BookmarkResp,
                             BookmarkUpdateReq)
from schemas.auth import MsgResp

router = APIRouter(prefix="/api/bookmarks", tags=["收藏"])


@router.post("", response_model=BookmarkResp)
def api_add(req: BookmarkReq, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    result = add_bookmark(db, user.id, req.transcription_id, req.tag, req.note)
    if not result:
        raise HTTPException(404, "句子不存在")
    return BookmarkResp(**result)


@router.delete("/by-transcription/{transcription_id}", response_model=MsgResp)
def api_remove_by_transcription(transcription_id: int,
                                 user: User = Depends(get_current_user),
                                 db: Session = Depends(get_db)):
    """按转录 ID 取消收藏（无需知道 bookmark_id）"""
    if not user:
        raise HTTPException(401, "请先登录")
    bookmark = db.query(Bookmark).filter(
        Bookmark.user_id == user.id,
        Bookmark.transcription_id == transcription_id
    ).first()
    if not bookmark:
        raise HTTPException(404, "收藏不存在")
    # 更新 transcription 标记
    db.query(Transcription).filter(
        Transcription.id == transcription_id
    ).update({"is_bookmarked": False})
    lecture = db.query(Lecture).filter(Lecture.id == bookmark.lecture_id).first()
    if lecture:
        lecture.bookmark_count = max(0, (lecture.bookmark_count or 0) - 1)
    db.delete(bookmark)
    db.commit()
    return MsgResp(message="已取消收藏")


@router.delete("/{bookmark_id}", response_model=MsgResp)
def api_remove(bookmark_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    if not remove_bookmark(db, user.id, bookmark_id):
        raise HTTPException(404, "收藏不存在")
    return MsgResp(message="已取消收藏")


@router.patch("/{bookmark_id}", response_model=BookmarkListItem)
def api_update(bookmark_id: int, request: BookmarkUpdateReq,
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    bookmark = db.query(Bookmark).filter(
        Bookmark.id == bookmark_id,
        Bookmark.user_id == user.id,
    ).first()
    if not bookmark:
        raise HTTPException(404, "收藏不存在")
    values = request.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(422, "至少提供一个需要更新的字段")
    if "tag" in values:
        bookmark.tag = values["tag"]
    if "note" in values:
        bookmark.note = values["note"].strip() or None if values["note"] else None
    db.commit()
    transcription = db.query(Transcription).filter(
        Transcription.id == bookmark.transcription_id,
        Transcription.user_id == user.id,
    ).first()
    lecture = db.query(Lecture).filter(
        Lecture.id == bookmark.lecture_id,
        Lecture.user_id == user.id,
    ).first()
    return BookmarkListItem(
        bookmark_id=bookmark.id,
        transcription_id=bookmark.transcription_id,
        lecture_id=bookmark.lecture_id,
        tag=bookmark.tag,
        note=bookmark.note,
        source_text=transcription.source_text if transcription else "",
        translated_text=transcription.translated_text if transcription else "",
        course_name=lecture.course_name if lecture else "",
        created_at=bookmark.created_at,
    )


@router.get("", response_model=list[BookmarkListItem])
def api_list(tag: Optional[str] = Query(None, pattern="^(important|question|exam|definition)$"),
             limit: int = Query(50, ge=1, le=100),
             user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    bookmarks = get_bookmarks(db, user.id, tag, limit=limit)
    transcription_ids = [b.transcription_id for b in bookmarks]
    lecture_ids = [b.lecture_id for b in bookmarks]
    transcriptions = {
        t.id: t for t in db.query(Transcription).filter(
            Transcription.id.in_(transcription_ids),
            Transcription.user_id == user.id,
        ).all()
    } if transcription_ids else {}
    lectures = {
        lecture.id: lecture for lecture in db.query(Lecture).filter(
            Lecture.id.in_(lecture_ids),
            Lecture.user_id == user.id,
        ).all()
    } if lecture_ids else {}
    result = []
    for b in bookmarks:
        t = transcriptions.get(b.transcription_id)
        lecture = lectures.get(b.lecture_id)
        result.append({
            "bookmark_id": b.id, "transcription_id": b.transcription_id,
            "lecture_id": b.lecture_id, "tag": b.tag, "note": b.note,
            "source_text": t.source_text if t else "",
            "translated_text": t.translated_text if t else "",
            "course_name": lecture.course_name if lecture else "",
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return result

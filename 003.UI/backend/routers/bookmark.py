"""LiveTrans Voice — 知识卡片(收藏)路由"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.lecture import Bookmark, Transcription
from routers.auth import get_current_user
from services.bookmark import add_bookmark, remove_bookmark, get_bookmarks
from schemas.lecture import BookmarkReq, BookmarkResp
from schemas.auth import MsgResp

router = APIRouter(prefix="/api/bookmarks", tags=["收藏"])


@router.post("", response_model=BookmarkResp)
def api_add(req: BookmarkReq, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    result = add_bookmark(db, user.id, req.transcription_id, req.tag)
    if not result:
        raise HTTPException(404, "句子不存在")
    return BookmarkResp(**result)


@router.delete("/{bookmark_id}", response_model=MsgResp)
def api_remove(bookmark_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    if not remove_bookmark(db, user.id, bookmark_id):
        raise HTTPException(404, "收藏不存在")
    return MsgResp(message="已取消收藏")


@router.get("", response_model=list[dict])
def api_list(tag: Optional[str] = Query(None, pattern="^(important|question|exam|definition)$"),
             user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    bookmarks = get_bookmarks(db, user.id, tag)
    result = []
    for b in bookmarks:
        t = db.query(Transcription).filter(Transcription.id == b.transcription_id).first()
        result.append({
            "bookmark_id": b.id, "tag": b.tag,
            "source_text": t.source_text if t else "",
            "translated_text": t.translated_text if t else "",
            "course_name": "", "created_at": b.created_at.isoformat() if b.created_at else None,
        })
    return result

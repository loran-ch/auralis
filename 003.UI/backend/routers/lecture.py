"""LiveTrans Voice — 课堂 + 转录路由"""
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from routers.auth import get_current_user
from services.lecture import (start_lecture, stop_lecture,
                               get_active_lecture, transcribe_audio, get_transcriptions)
from schemas.lecture import StartLectureReq, LectureResp, TranscriptionResp
from schemas.auth import MsgResp

router = APIRouter(prefix="/api/lectures", tags=["课堂"])


@router.post("/start", response_model=LectureResp)
def api_start(req: StartLectureReq, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    # 先结束之前的课堂
    active = get_active_lecture(db, user.id)
    if active:
        stop_lecture(db, active.id, user.id)
    lecture = start_lecture(db, user.id, req.course_name, req.source_lang, req.target_lang)
    return LectureResp.model_validate(lecture)


@router.post("/{lecture_id}/stop", response_model=LectureResp)
def api_stop(lecture_id: int, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = stop_lecture(db, lecture_id, user.id)
    if not lecture:
        raise HTTPException(404, "课堂不存在")
    return LectureResp.model_validate(lecture)


@router.get("")
def api_list(user: User = Depends(get_current_user), db: Session = Depends(get_db),
             page: int = 1, size: int = 15):
    if not user:
        raise HTTPException(401, "请先登录")
    from models.lecture import Lecture
    query = db.query(Lecture).filter(
        Lecture.user_id == user.id, Lecture.status == "completed"
    )
    total = query.count()
    lectures = query.order_by(Lecture.lecture_date.asc()).offset((page-1)*size).limit(size).all()
    return {
        "items": [LectureResp.model_validate(l) for l in lectures],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size)
    }


class RenameReq(BaseModel):
    course_name: str = Field(..., min_length=1, max_length=256)


@router.delete("/{lecture_id}")
def api_delete(lecture_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    from models.lecture import Lecture, Transcription, Bookmark
    lecture = db.query(Lecture).filter(Lecture.id == lecture_id, Lecture.user_id == user.id).first()
    if not lecture:
        raise HTTPException(404, "课堂不存在")
    # 级联删除: 收藏 → 转录 → 课堂
    db.query(Bookmark).filter(Bookmark.lecture_id == lecture_id).delete()
    db.query(Transcription).filter(Transcription.lecture_id == lecture_id).delete()
    db.delete(lecture)
    db.commit()
    return {"message": "已删除"}


@router.put("/{lecture_id}/rename", response_model=LectureResp)
def api_rename(lecture_id: int, req: RenameReq, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    from models.lecture import Lecture
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = db.query(Lecture).filter(Lecture.id == lecture_id, Lecture.user_id == user.id).first()
    if not lecture:
        raise HTTPException(404, "课堂不存在")
    lecture.course_name = req.course_name
    db.commit()
    db.refresh(lecture)
    return LectureResp.model_validate(lecture)


@router.get("/active", response_model=Optional[LectureResp])
def api_active(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        return None
    lecture = get_active_lecture(db, user.id)
    return LectureResp.model_validate(lecture) if lecture else None


class TranscribeTextReq(BaseModel):
    source_text: str = ""
    translated_text: str = ""


@router.post("/{lecture_id}/transcribe/text")
def api_transcribe_text(lecture_id: int, req: TranscribeTextReq,
                         user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """保存前端语音识别结果"""
    if not user:
        raise HTTPException(401, "请先登录")
    result = transcribe_audio(db, lecture_id, user.id, req.source_text, req.translated_text)
    if not result:
        raise HTTPException(404, "课堂不存在或已结束")
    return TranscriptionResp(**result)


@router.post("/{lecture_id}/transcribe")
async def api_transcribe(lecture_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db),
                   audio: UploadFile = File(None)):
    """演示模式: 无音频时返回预设句子"""
    if not user:
        raise HTTPException(401, "请先登录")
    result = transcribe_audio(db, lecture_id, user.id)
    if not result:
        raise HTTPException(404, "课堂不存在或已结束")
    if result.get("done"):
        return {}
    return TranscriptionResp(**result)


@router.get("/{lecture_id}/transcriptions", response_model=list[TranscriptionResp])
def api_transcriptions(lecture_id: int, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    items = get_transcriptions(db, lecture_id, user.id)
    return [TranscriptionResp.model_validate(t) for t in items]

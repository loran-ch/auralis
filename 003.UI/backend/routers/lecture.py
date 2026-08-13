"""LiveTrans Voice — 课堂 + 转录路由"""
from typing import Optional
from datetime import date
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File, Form, Query
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from config import ASR_MAX_SEGMENT_MB, IS_PRODUCTION, MAX_AUDIO_SIZE_MB
from database import get_db
from models.lecture import Bookmark, Lecture, Transcription
from models.user import User
from routers.auth import get_current_user
from services.lecture import (start_lecture, stop_lecture,
                               get_active_lecture, transcribe_audio, get_transcriptions,
                               get_lecture, pause_lecture, resume_lecture)
from services.preferences import language_exists
from services.speech_recognizer import (SpeechRecognitionNoSpeech,
                                        SpeechRecognitionUnavailable,
                                        recognize_speech)
from services.translator import translate_with_status
from schemas.lecture import (StartLectureReq, LectureResp, LectureUpdateReq,
                             TranscriptionResp)

router = APIRouter(prefix="/api/lectures", tags=["课堂"])


@router.post("/start", response_model=LectureResp)
def api_start(req: StartLectureReq, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    if not language_exists(db, req.source_lang) or not language_exists(db, req.target_lang):
        raise HTTPException(422, "不支持的翻译语言")
    # 同一用户只允许一个活动课堂；开始新课堂时结束旧课堂。
    active = get_active_lecture(db, user.id)
    if active:
        stop_lecture(db, active.id, user.id)
    lecture = start_lecture(db, user.id, req.course_name, req.source_lang, req.target_lang)
    return LectureResp.model_validate(lecture)


@router.post("/{lecture_id}/pause", response_model=LectureResp)
def api_pause(lecture_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = pause_lecture(db, lecture_id, user.id)
    if not lecture:
        raise HTTPException(409, "课堂不存在或当前状态无法暂停")
    return LectureResp.model_validate(lecture)


@router.post("/{lecture_id}/resume", response_model=LectureResp)
def api_resume(lecture_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = resume_lecture(db, lecture_id, user.id)
    if not lecture:
        raise HTTPException(409, "课堂不存在或当前状态无法恢复")
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
             page: int = Query(1, ge=1), size: int = Query(15, ge=1, le=100),
             search: Optional[str] = Query(default=None, max_length=128),
             date_from: Optional[date] = Query(default=None),
             date_to: Optional[date] = Query(default=None),
             status: str = Query("completed", pattern=r"^(completed|recording|paused|failed|all)$")):
    if not user:
        raise HTTPException(401, "请先登录")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    query = db.query(Lecture).filter(Lecture.user_id == user.id)
    if status != "all":
        query = query.filter(Lecture.status == status)
    # 搜索：按课程名称模糊匹配
    if search:
        query = query.filter(Lecture.course_name.ilike(f"%{search.strip()}%"))
    # 日期筛选
    if date_from:
        query = query.filter(Lecture.lecture_date >= date_from)
    if date_to:
        query = query.filter(Lecture.lecture_date <= date_to)
    total = query.count()
    lectures = query.order_by(
        Lecture.lecture_date.desc(), Lecture.started_at.desc(), Lecture.id.desc()
    ).offset((page-1)*size).limit(size).all()
    return {
        "items": [LectureResp.model_validate(l) for l in lectures],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, (total + size - 1) // size)
    }


class BatchDeleteReq(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=50)


@router.post("/batch-delete")
def api_batch_delete(req: BatchDeleteReq, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    requested_ids = list(set(req.ids))
    owned_rows = db.query(Lecture.id, Lecture.audio_url).filter(
        Lecture.id.in_(requested_ids), Lecture.user_id == user.id
    ).all()
    owned_ids = [row.id for row in owned_rows]
    deleted = len(owned_ids)
    if owned_ids:
        db.query(Bookmark).filter(Bookmark.lecture_id.in_(owned_ids)).delete(
            synchronize_session=False
        )
        db.query(Transcription).filter(Transcription.lecture_id.in_(owned_ids)).delete(
            synchronize_session=False
        )
        db.query(Lecture).filter(Lecture.id.in_(owned_ids)).delete(
            synchronize_session=False
        )
    db.commit()
    for row in owned_rows:
        _remove_local_audio(row.audio_url)
    return {"message": "已删除 " + str(deleted) + " 条记录", "deleted": deleted}


class RenameReq(BaseModel):
    course_name: str = Field(..., min_length=1, max_length=256)


@router.get("/active", response_model=Optional[LectureResp])
def api_active(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = get_active_lecture(db, user.id)
    return LectureResp.model_validate(lecture) if lecture else None


@router.get("/{lecture_id}", response_model=LectureResp)
def api_detail(lecture_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = get_lecture(db, lecture_id, user.id)
    if not lecture:
        raise HTTPException(404, "课堂不存在")
    return LectureResp.model_validate(lecture)


@router.patch("/{lecture_id}", response_model=LectureResp)
def api_update(lecture_id: int, request: LectureUpdateReq,
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = get_lecture(db, lecture_id, user.id)
    if not lecture:
        raise HTTPException(404, "课堂不存在")
    values = request.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(422, "至少提供一个需要更新的字段")
    if "course_name" in values and not values["course_name"]:
        raise HTTPException(422, "课程名称不能为空")
    for field, value in values.items():
        setattr(lecture, field, value)
    db.commit()
    db.refresh(lecture)
    return LectureResp.model_validate(lecture)


AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "uploads" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def _detect_audio_extension(header: bytes) -> Optional[str]:
    if header.startswith(b"ID3"):
        return ".mp3"
    if len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0:
        return ".mp3"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return ".webm"
    if header.startswith(b"OggS"):
        return ".ogg"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return ".wav"
    if len(header) >= 8 and header[4:8] == b"ftyp":
        return ".m4a"
    return None


def _remove_local_audio(audio_url: Optional[str]) -> None:
    """只删除本项目音频目录中的文件，避免路径穿越和孤儿文件。"""
    if not audio_url or not audio_url.startswith("/uploads/audio/"):
        return
    candidate = (AUDIO_DIR / Path(audio_url).name).resolve()
    if candidate.parent == AUDIO_DIR.resolve():
        candidate.unlink(missing_ok=True)


def _write_audio_segment(lecture: Lecture, user_id: int, contents: bytes,
                         extension: str, append: bool) -> dict:
    """把已校验的短分片写入课堂录音，返回可用于提交或回滚的状态。"""
    old_audio_url = lecture.audio_url
    appending_existing = False
    previous_size = 0
    if append and old_audio_url and old_audio_url.startswith("/uploads/audio/"):
        candidate = (AUDIO_DIR / Path(old_audio_url).name).resolve()
        if candidate.parent != AUDIO_DIR.resolve() or not candidate.is_file():
            raise HTTPException(409, "原录音文件不存在，无法追加分片")
        if candidate.suffix.lower() != extension:
            raise HTTPException(409, "录音分片格式与原录音不一致")
        filepath = candidate
        filename = candidate.name
        previous_size = candidate.stat().st_size
        appending_existing = True
    else:
        filename = f"{user_id}_{lecture.id}_{uuid.uuid4().hex[:10]}{extension}"
        filepath = AUDIO_DIR / filename

    limit = MAX_AUDIO_SIZE_MB * 1024 * 1024
    if previous_size + len(contents) > limit:
        raise HTTPException(413, f"音频不能超过 {MAX_AUDIO_SIZE_MB}MB")
    try:
        with filepath.open("ab" if appending_existing else "wb") as output:
            output.write(contents)
    except Exception:
        if appending_existing and filepath.exists():
            with filepath.open("r+b") as output:
                output.truncate(previous_size)
        else:
            filepath.unlink(missing_ok=True)
        raise
    return {
        "filepath": filepath,
        "filename": filename,
        "old_audio_url": old_audio_url,
        "previous_size": previous_size,
        "new_size": previous_size + len(contents),
        "appending_existing": appending_existing,
    }


def _rollback_audio_segment(state: dict) -> None:
    filepath = state["filepath"]
    if state["appending_existing"] and filepath.exists():
        with filepath.open("r+b") as output:
            output.truncate(state["previous_size"])
    else:
        filepath.unlink(missing_ok=True)


@router.post("/{lecture_id}/audio", response_model=LectureResp)
async def api_upload_audio(lecture_id: int, file: UploadFile = File(...),
                           append: bool = Form(False),
                           user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = get_lecture(db, lecture_id, user.id)
    if not lecture:
        raise HTTPException(404, "课堂不存在")

    first_chunk = await file.read(4096)
    extension = _detect_audio_extension(first_chunk)
    if not extension:
        raise HTTPException(400, "仅支持 MP3/WEBM/OGG/WAV/M4A 音频")

    old_audio_url = lecture.audio_url
    appending_existing = False
    previous_size = 0
    if append and old_audio_url and old_audio_url.startswith("/uploads/audio/"):
        candidate = (AUDIO_DIR / Path(old_audio_url).name).resolve()
        if candidate.parent != AUDIO_DIR.resolve() or not candidate.is_file():
            raise HTTPException(409, "原录音文件不存在，无法追加分片")
        if candidate.suffix.lower() != extension:
            raise HTTPException(409, "录音分片格式与原录音不一致")
        filepath = candidate
        filename = candidate.name
        previous_size = candidate.stat().st_size
        appending_existing = True
    else:
        filename = f"{user.id}_{lecture.id}_{uuid.uuid4().hex[:10]}{extension}"
        filepath = AUDIO_DIR / filename

    limit = MAX_AUDIO_SIZE_MB * 1024 * 1024
    written = 0
    try:
        with filepath.open("ab" if appending_existing else "wb") as output:
            chunk = first_chunk
            while chunk:
                written += len(chunk)
                if previous_size + written > limit:
                    raise HTTPException(413, f"音频不能超过 {MAX_AUDIO_SIZE_MB}MB")
                output.write(chunk)
                chunk = await file.read(1024 * 1024)
    except Exception:
        if appending_existing:
            with filepath.open("r+b") as output:
                output.truncate(previous_size)
        else:
            filepath.unlink(missing_ok=True)
        raise

    lecture.audio_url = f"/uploads/audio/{filename}"
    lecture.audio_size_bytes = previous_size + written
    try:
        db.commit()
    except Exception:
        db.rollback()
        if appending_existing:
            with filepath.open("r+b") as output:
                output.truncate(previous_size)
        else:
            filepath.unlink(missing_ok=True)
        raise
    db.refresh(lecture)
    if not appending_existing and old_audio_url != lecture.audio_url:
        _remove_local_audio(old_audio_url)
    return LectureResp.model_validate(lecture)


@router.delete("/{lecture_id}")
def api_delete(lecture_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = db.query(Lecture).filter(Lecture.id == lecture_id, Lecture.user_id == user.id).first()
    if not lecture:
        raise HTTPException(404, "课堂不存在")
    # 级联删除: 收藏 → 转录 → 课堂
    db.query(Bookmark).filter(Bookmark.lecture_id == lecture_id).delete()
    db.query(Transcription).filter(Transcription.lecture_id == lecture_id).delete()
    audio_url = lecture.audio_url
    db.delete(lecture)
    db.commit()
    _remove_local_audio(audio_url)
    return {"message": "已删除"}


@router.put("/{lecture_id}/rename", response_model=LectureResp)
def api_rename(lecture_id: int, req: RenameReq, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = db.query(Lecture).filter(Lecture.id == lecture_id, Lecture.user_id == user.id).first()
    if not lecture:
        raise HTTPException(404, "课堂不存在")
    course_name = req.course_name.strip()
    if not course_name:
        raise HTTPException(422, "课程名称不能为空")
    lecture.course_name = course_name
    db.commit()
    db.refresh(lecture)
    return LectureResp.model_validate(lecture)


class TranscribeTextReq(BaseModel):
    source_text: str = Field(..., min_length=1, max_length=4000)
    translated_text: str = Field(default="", max_length=8000)

    @field_validator("source_text")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("识别内容不能为空")
        return value


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


@router.post("/{lecture_id}/transcribe/audio", response_model=TranscriptionResp)
async def api_transcribe_audio_segment(
    lecture_id: int,
    file: UploadFile = File(...),
    append: bool = Form(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """一次上传完成录音保存、识别、翻译和持久化。"""
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = get_lecture(db, lecture_id, user.id)
    if not lecture or lecture.status not in {"recording", "paused"}:
        raise HTTPException(409, "课堂不存在或已结束")
    contents = await file.read(ASR_MAX_SEGMENT_MB * 1024 * 1024 + 1)
    if not contents:
        raise HTTPException(400, "音频内容为空")
    if len(contents) > ASR_MAX_SEGMENT_MB * 1024 * 1024:
        raise HTTPException(413, f"识别分片不能超过 {ASR_MAX_SEGMENT_MB}MB")
    extension = _detect_audio_extension(contents[:4096])
    if not extension:
        raise HTTPException(400, "不支持的音频格式")

    # 先持久化录音并提交短事务。外部 ASR/翻译调用期间不占用数据库连接。
    source_lang = lecture.source_lang
    target_lang = lecture.target_lang
    audio_state = await run_in_threadpool(
        _write_audio_segment, lecture, user.id, contents, extension, append
    )
    new_audio_url = f"/uploads/audio/{audio_state['filename']}"
    lecture.audio_url = new_audio_url
    lecture.audio_size_bytes = audio_state["new_size"]
    try:
        db.commit()
    except Exception:
        db.rollback()
        await run_in_threadpool(_rollback_audio_segment, audio_state)
        raise
    if (not audio_state["appending_existing"] and
            audio_state["old_audio_url"] != new_audio_url):
        await run_in_threadpool(_remove_local_audio, audio_state["old_audio_url"])

    try:
        source_text = await run_in_threadpool(
            recognize_speech, contents, extension, source_lang
        )
    except SpeechRecognitionNoSpeech:
        # 静音、环境噪音或停止录音时产生的过短尾段属于正常情况。
        # 音频已经保存；返回 204 让客户端静默跳过本次转录。
        return Response(status_code=204)
    except SpeechRecognitionUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    translation = await run_in_threadpool(
        translate_with_status,
        source_text,
        source_lang,
        target_lang,
    )
    result = transcribe_audio(
        db, lecture_id, user.id, source_text, translation["text"]
    )
    if not result:
        raise HTTPException(409, "课堂已结束，识别结果未保存")
    return TranscriptionResp(
        **result,
        translation_success=translation["success"],
        translation_provider=translation["provider"],
        translation_warning=translation["warning"],
    )


@router.post("/{lecture_id}/transcribe")
def api_transcribe(lecture_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """演示模式: 无音频时返回预设句子"""
    if not user:
        raise HTTPException(401, "请先登录")
    if IS_PRODUCTION:
        raise HTTPException(503, "生产环境未启用演示转录")
    if not get_lecture(db, lecture_id, user.id):
        raise HTTPException(404, "课堂不存在")
    result = transcribe_audio(db, lecture_id, user.id)
    if not result:
        raise HTTPException(404, "课堂不存在或已结束")
    if result.get("done"):
        return {}
    return TranscriptionResp(**result)


@router.get("/{lecture_id}/transcriptions", response_model=list[TranscriptionResp])
def api_transcriptions(lecture_id: int, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db),
                       limit: int = Query(100, ge=1, le=200)):
    if not user:
        raise HTTPException(401, "请先登录")
    items = get_transcriptions(db, lecture_id, user.id, limit=limit)
    from models.lecture import Bookmark
    bookmarked_ids = [t.id for t in items if t.is_bookmarked]
    bookmark_tags = {}
    if bookmarked_ids:
        bookmark_tags = dict(db.query(
            Bookmark.transcription_id, Bookmark.tag
        ).filter(
            Bookmark.user_id == user.id,
            Bookmark.transcription_id.in_(bookmarked_ids),
        ).all())
    result = []
    for t in items:
        d = TranscriptionResp.model_validate(t)
        d.bookmark_tag = bookmark_tags.get(t.id)
        result.append(d)
    return result

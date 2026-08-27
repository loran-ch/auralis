"""LiveTrans Voice — 课堂 + 转录路由"""
from typing import Optional
from datetime import date
from pathlib import Path
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, UploadFile, File, Form, Query
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session
from config import (ASR_MAX_SEGMENT_MB, IS_PRODUCTION, MAX_ATTACHMENT_SIZE_MB,
                    MAX_AUDIO_SIZE_MB, MAX_VIDEO_SIZE_MB)
from database import SessionLocal, get_db
from models.lecture import (Bookmark, Lecture, LectureBriefing, MediaAsset,
                            MediaClipCandidate, Transcription, TranscriptionVerification)
from models.user import User
from routers.auth import get_current_user
from services.assistant import answer_lecture_question
from services.attachments import (ALLOWED_CONTENT_TYPES, ATTACHMENT_CATEGORIES,
                                  attachment_to_dict, create_attachment,
                                  delete_attachment, ensure_attachment_table,
                                  extension_for_upload, get_attachment,
                                  list_attachments, max_upload_mb_for)
from services.briefing import (briefing_to_dict, confirm_briefing_assignment,
                               delete_briefing_assignment, generate_briefing,
                               get_briefing, patch_briefing, supplement_briefing_item)
from services.export_pack import (build_briefing_markdown, build_materials_zip,
                                  content_disposition)
from services.lecture import (stop_lecture,
                               get_active_lecture, transcribe_audio, get_transcriptions,
                               get_lecture, can_manage_lecture, pause_lecture, resume_lecture,
                               begin_lecture_session, reopen_lecture_for_append,
                               get_recent_source_sentences)
from services.llm_quota import QuotaExceededError
from services.preferences import language_exists
from services.courses import get_course, get_readable_course
from services.speech_recognizer import (SpeechRecognitionNoSpeech,
                                        SpeechRecognitionUnavailable,
                                        recognize_speech)
from services.translator import translate_with_context
from services.media import (export_clip, generate_clip_candidates,
                            process_lecture_media, verify_transcription)
from schemas.lecture import (StartLectureReq, LectureResp, LectureUpdateReq,
                             TranscriptionResp, GenerateBriefingReq, BriefingResp,
                             BriefingPatchReq, BriefingSupplementReq,
                             LectureAttachmentResp, AssistantAskReq, AssistantAskResp)

router = APIRouter(prefix="/api/lectures", tags=["课堂"])
logger = logging.getLogger(__name__)


def _readable_lecture(db: Session, lecture_id: int, user: User) -> Lecture:
    lecture = get_lecture(db, lecture_id, user.id)
    if not lecture:
        raise HTTPException(404, "课堂不存在")
    return lecture


def _manageable_lecture(db: Session, lecture_id: int, user: User) -> Lecture:
    lecture = get_lecture(db, lecture_id, user.id)
    if not lecture or not can_manage_lecture(lecture, user.id):
        raise HTTPException(404, "课堂不存在")
    return lecture


def _generate_briefing_job(lecture_id: int, user_id: int, force: bool = False) -> None:
    db = SessionLocal()
    try:
        generate_briefing(db, lecture_id, user_id, force=force)
    except Exception:
        logger.exception("课堂简报后台生成失败 lecture_id=%s", lecture_id)
    finally:
        db.close()


def _process_lecture_media_job(lecture_id: int, user_id: int) -> None:
    db = SessionLocal()
    try:
        process_lecture_media(db, lecture_id, user_id)
        generate_clip_candidates(db, lecture_id, user_id)
    except Exception:
        logger.exception("课堂媒体处理失败 lecture_id=%s", lecture_id)
    finally:
        db.close()


def _export_clip_job(candidate_id: int, user_id: int) -> None:
    db = SessionLocal()
    try:
        candidate = db.query(MediaClipCandidate).filter(
            MediaClipCandidate.id == candidate_id, MediaClipCandidate.user_id == user_id,
        ).first()
        if candidate:
            export_clip(db, candidate)
    except Exception:
        logger.exception("课堂短片导出失败 candidate_id=%s", candidate_id)
    finally:
        db.close()


def _verify_transcription_job(verification_id: int, user_id: int) -> None:
    db = SessionLocal()
    try:
        verification = db.query(TranscriptionVerification).filter(
            TranscriptionVerification.id == verification_id,
            TranscriptionVerification.user_id == user_id,
        ).first()
        if not verification:
            return
        lecture = get_lecture(db, verification.lecture_id, user_id)
        transcription = db.query(Transcription).filter(
            Transcription.id == verification.transcription_id,
            Transcription.user_id == user_id,
        ).first()
        if not lecture or not transcription:
            verification.status, verification.error_message = "failed", "课堂或原始转录不存在"
            db.commit()
            return
        verify_transcription(db, verification, lecture, transcription)
    except Exception:
        logger.exception("转录二次核验失败 verification_id=%s", verification_id)
    finally:
        db.close()


@router.post("/start", response_model=LectureResp)
def api_start(req: StartLectureReq, background_tasks: BackgroundTasks,
              user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    course = None
    if req.course_id:
        course = get_course(db, user.id, req.course_id, include_inactive=False)
        if not course:
            raise HTTPException(404, "课程不存在或已归档")
    source_lang = course.source_lang if course else req.source_lang
    requested_translation = req.translation_enabled
    translation_enabled = (
        course.translation_enabled if course and requested_translation is None
        else (False if requested_translation is None else requested_translation)
    )
    target_preference = course.target_lang if course else req.target_lang
    course_name = course.name if course else req.course_name
    if not language_exists(db, source_lang):
        raise HTTPException(422, "不支持的翻译语言")
    if translation_enabled and not language_exists(db, target_preference):
        raise HTTPException(422, "不支持的翻译语言")
    target_lang = target_preference if translation_enabled else source_lang
    lecture, resumed, stopped = begin_lecture_session(
        db, user.id, course_name, source_lang, target_lang,
        translation_enabled, course.id if course else None,
        force_new=bool(req.force_new),
    )
    if stopped:
        background_tasks.add_task(_generate_briefing_job, stopped.id, user.id)
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


@router.post("/{lecture_id}/append", response_model=LectureResp)
def api_append(lecture_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """对已结束课堂开启补录（重新进入 recording，保留已有字幕）。"""
    if not user:
        raise HTTPException(401, "请先登录")
    try:
        lecture = reopen_lecture_for_append(db, lecture_id, user.id)
    except LookupError:
        raise HTTPException(404, "课堂不存在") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return LectureResp.model_validate(lecture)


@router.post("/{lecture_id}/stop", response_model=LectureResp)
def api_stop(lecture_id: int, background_tasks: BackgroundTasks,
             user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = stop_lecture(db, lecture_id, user.id)
    if not lecture:
        raise HTTPException(404, "课堂不存在")
    existing = get_briefing(db, lecture.id, user.id)
    force_briefing = (
        not existing
        or (existing.source_sentence_count or 0) < (lecture.sentence_count or 0)
        or existing.status in {"empty", "failed"}
    )
    background_tasks.add_task(_generate_briefing_job, lecture.id, user.id, force_briefing)
    background_tasks.add_task(_process_lecture_media_job, lecture.id, user.id)
    return LectureResp.model_validate(lecture)


@router.get("")
def api_list(user: User = Depends(get_current_user), db: Session = Depends(get_db),
             page: int = Query(1, ge=1), size: int = Query(15, ge=1, le=100),
             search: Optional[str] = Query(default=None, max_length=128),
             date_from: Optional[date] = Query(default=None),
             date_to: Optional[date] = Query(default=None),
             course_id: Optional[int] = Query(default=None, gt=0),
             unassigned: bool = Query(default=False),
             status: str = Query("completed", pattern=r"^(completed|recording|paused|failed|all)$")):
    if not user:
        raise HTTPException(401, "请先登录")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    if course_id and unassigned:
        raise HTTPException(422, "不能同时筛选课程和未归类记录")
    content_user_id = user.id
    if course_id:
        course = get_readable_course(db, user, course_id)
        if not course:
            raise HTTPException(404, "课程不存在或无权访问")
        content_user_id = int(course.user_id)
        # 公开课访客只读已完成课次。
        if int(course.user_id) != int(user.id) and status not in ("completed", "all"):
            status = "completed"
    query = db.query(Lecture).filter(Lecture.user_id == content_user_id)
    if status != "all":
        query = query.filter(Lecture.status == status)
    # 搜索：按课程名称模糊匹配
    if search:
        query = query.filter(Lecture.course_name.ilike(f"%{search.strip()}%"))
    if course_id:
        # 同时以可读课程约束，避免用不存在或其他用户的课程 ID 探测数据。
        query = query.filter(Lecture.course_id == course_id)
        if int(content_user_id) != int(user.id):
            query = query.filter(Lecture.status == "completed")
    elif unassigned:
        query = query.filter(Lecture.course_id.is_(None))
        query = query.filter(Lecture.user_id == user.id)
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
        db.query(LectureBriefing).filter(LectureBriefing.lecture_id.in_(owned_ids)).delete(
            synchronize_session=False
        )
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
    title: Optional[str] = Field(None, min_length=1, max_length=256)
    # 兼容旧版客户端；关联课程的旧请求也只会修改课堂标题。
    course_name: Optional[str] = Field(None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def validate_title(self):
        value = (self.title or self.course_name or "").strip()
        if not value:
            raise ValueError("课堂标题不能为空")
        self.title = value
        return self


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
    lecture = _readable_lecture(db, lecture_id, user)
    return LectureResp.model_validate(lecture)


@router.patch("/{lecture_id}", response_model=LectureResp)
def api_update(lecture_id: int, request: LectureUpdateReq,
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = _manageable_lecture(db, lecture_id, user)
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
MEDIA_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "uploads" / "media"
VIDEO_DIR = MEDIA_DIR / "video"
FRAME_DIR = MEDIA_DIR / "frames"
ATTACHMENT_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "uploads" / "attachments"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)
FRAME_DIR.mkdir(parents=True, exist_ok=True)
ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)


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


def _detect_video_extension(header: bytes) -> Optional[str]:
    if header.startswith(b"\x1aE\xdf\xa3"):
        return ".webm"
    if len(header) >= 8 and header[4:8] == b"ftyp":
        return ".mp4"
    return None


def _detect_image_extension(header: bytes) -> Optional[str]:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    return None


def _remove_local_media(url: Optional[str]) -> None:
    if not url or not url.startswith("/uploads/media/"):
        return
    candidate = (MEDIA_DIR / Path(url).relative_to("/uploads/media/")).resolve()
    if MEDIA_DIR.resolve() in candidate.parents:
        candidate.unlink(missing_ok=True)


async def _save_media_upload(file: UploadFile, destination: Path, limit_mb: int) -> int:
    written = 0
    with destination.open("ab") as output:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if destination.stat().st_size + len(chunk) > limit_mb * 1024 * 1024:
                raise HTTPException(413, f"媒体文件不能超过 {limit_mb}MB")
            output.write(chunk)
    return written


@router.post("/{lecture_id}/media/video")
async def api_upload_video(lecture_id: int, file: UploadFile = File(...), append: bool = Form(False),
                           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """录像按分片顺序追加；任何失败都不影响音频和转录保存。"""
    if not user:
        raise HTTPException(401, "请先登录")
    _manageable_lecture(db, lecture_id, user)
    first = await file.read(4096)
    ext = _detect_video_extension(first)
    if not ext:
        raise HTTPException(400, "仅支持 WEBM 或 MP4 视频")
    asset = None
    if append:
        asset = db.query(MediaAsset).filter(
            MediaAsset.lecture_id == lecture_id, MediaAsset.user_id == user.id,
            MediaAsset.media_type == "video",
        ).order_by(MediaAsset.id.desc()).first()
    if asset:
        path = (MEDIA_DIR / Path(asset.url).relative_to("/uploads/media/")).resolve()
        if path.parent != VIDEO_DIR.resolve() or path.suffix.lower() != ext:
            raise HTTPException(409, "视频分片格式与已有录像不一致")
    else:
        filename = f"{user.id}_{lecture_id}_{uuid.uuid4().hex[:10]}{ext}"
        path = (VIDEO_DIR / filename).resolve()
        asset = MediaAsset(
            lecture_id=lecture_id, user_id=user.id, media_type="video", status="uploaded",
            url=f"/uploads/media/video/{filename}", content_type=file.content_type,
        )
        db.add(asset)
    try:
        with path.open("ab") as output:
            output.write(first)
        await _save_media_upload(file, path, MAX_VIDEO_SIZE_MB)
    except Exception:
        if not asset.id:
            db.rollback()
            path.unlink(missing_ok=True)
        raise
    asset.size_bytes = path.stat().st_size
    asset.status = "ready"
    db.commit()
    db.refresh(asset)
    return {"id": asset.id, "url": asset.url, "size_bytes": asset.size_bytes, "status": asset.status}


@router.post("/{lecture_id}/media/frame")
async def api_upload_video_frame(lecture_id: int, file: UploadFile = File(...),
                                 start_offset_ms: int = Form(0, ge=0),
                                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """浏览器在画面变化时上传候选关键帧；OCR 后续异步接管。"""
    if not user:
        raise HTTPException(401, "请先登录")
    _manageable_lecture(db, lecture_id, user)
    first = await file.read(4096)
    ext = _detect_image_extension(first)
    if not ext:
        raise HTTPException(400, "仅支持 PNG 或 JPEG 关键帧")
    filename = f"{user.id}_{lecture_id}_{start_offset_ms}_{uuid.uuid4().hex[:8]}{ext}"
    path = (FRAME_DIR / filename).resolve()
    with path.open("wb") as output:
        output.write(first)
    try:
        await _save_media_upload(file, path, 10)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    asset = MediaAsset(
        lecture_id=lecture_id, user_id=user.id, media_type="frame", status="uploaded",
        url=f"/uploads/media/frames/{filename}", content_type=file.content_type,
        size_bytes=path.stat().st_size, start_offset_ms=start_offset_ms,
        metadata_json={"ocr_status": "pending"},
    )
    db.add(asset)
    db.commit()
    return {"id": asset.id, "url": asset.url, "start_offset_ms": asset.start_offset_ms, "status": asset.status}


@router.get("/{lecture_id}/media")
def api_list_media(lecture_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = _readable_lecture(db, lecture_id, user)
    owner_id = lecture.user_id
    assets = db.query(MediaAsset).filter(
        MediaAsset.lecture_id == lecture_id, MediaAsset.user_id == owner_id,
    ).order_by(MediaAsset.media_type, MediaAsset.start_offset_ms, MediaAsset.id).all()
    clips = db.query(MediaClipCandidate).filter(
        MediaClipCandidate.lecture_id == lecture_id, MediaClipCandidate.user_id == owner_id,
    ).order_by(MediaClipCandidate.score.desc(), MediaClipCandidate.id.desc()).all()
    return {
        "assets": [{"id": x.id, "type": x.media_type, "status": x.status, "url": x.url,
                    "content_type": x.content_type, "size_bytes": x.size_bytes,
                    "start_offset_ms": x.start_offset_ms, "metadata": x.metadata_json or {},
                    "error_message": x.error_message} for x in assets],
        "clips": [{"id": x.id, "title": x.title, "reason": x.reason,
                   "start_offset_ms": x.start_offset_ms, "end_offset_ms": x.end_offset_ms,
                   "score": x.score, "status": x.status, "media_url": x.media_url,
                   "error_message": x.error_message} for x in clips],
    }


@router.post("/{lecture_id}/media/process", status_code=202)
def api_process_media(lecture_id: int, background_tasks: BackgroundTasks,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    _manageable_lecture(db, lecture_id, user)
    background_tasks.add_task(_process_lecture_media_job, lecture_id, user.id)
    return {"status": "processing"}


@router.post("/{lecture_id}/media/clips/{candidate_id}/export", status_code=202)
def api_export_clip(lecture_id: int, candidate_id: int, background_tasks: BackgroundTasks,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    candidate = db.query(MediaClipCandidate).filter(
        MediaClipCandidate.id == candidate_id, MediaClipCandidate.lecture_id == lecture_id,
        MediaClipCandidate.user_id == user.id,
    ).first()
    if not candidate:
        raise HTTPException(404, "候选短片不存在")
    if candidate.status == "exporting":
        return {"id": candidate.id, "status": candidate.status}
    candidate.status, candidate.error_message = "exporting", None
    db.commit()
    background_tasks.add_task(_export_clip_job, candidate.id, user.id)
    return {"id": candidate.id, "status": candidate.status}


@router.post("/{lecture_id}/transcriptions/{transcription_id}/verify", status_code=202)
def api_verify_transcription(lecture_id: int, transcription_id: int, background_tasks: BackgroundTasks,
                             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    _manageable_lecture(db, lecture_id, user)
    transcription = db.query(Transcription).filter(
        Transcription.id == transcription_id, Transcription.lecture_id == lecture_id,
        Transcription.user_id == user.id,
    ).first()
    if not transcription:
        raise HTTPException(404, "课堂转录不存在")
    verification = TranscriptionVerification(
        lecture_id=lecture_id, transcription_id=transcription_id, user_id=user.id,
        status="processing", original_text=transcription.source_text,
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)
    background_tasks.add_task(_verify_transcription_job, verification.id, user.id)
    return {"id": verification.id, "status": verification.status}


@router.get("/{lecture_id}/transcriptions/{transcription_id}/verifications")
def api_list_verifications(lecture_id: int, transcription_id: int,
                           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    rows = db.query(TranscriptionVerification).filter(
        TranscriptionVerification.lecture_id == lecture_id,
        TranscriptionVerification.transcription_id == transcription_id,
        TranscriptionVerification.user_id == user.id,
    ).order_by(TranscriptionVerification.id.desc()).limit(10).all()
    return [{"id": x.id, "status": x.status, "original_text": x.original_text,
             "suggested_text": x.suggested_text, "secondary_asr": x.secondary_asr,
             "evidence": x.evidence_json or {}, "error_message": x.error_message,
             "created_at": x.created_at} for x in rows]


@router.post("/{lecture_id}/transcriptions/{transcription_id}/verifications/{verification_id}/confirm")
def api_confirm_verification(lecture_id: int, transcription_id: int, verification_id: int,
                             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    verification = db.query(TranscriptionVerification).filter(
        TranscriptionVerification.id == verification_id, TranscriptionVerification.lecture_id == lecture_id,
        TranscriptionVerification.transcription_id == transcription_id, TranscriptionVerification.user_id == user.id,
    ).first()
    if not verification:
        raise HTTPException(404, "核验记录不存在")
    if verification.status != "suggested":
        raise HTTPException(409, "当前核验没有可确认的修正建议")
    # 不覆盖课堂原文：确认仅表示用户认可该候选版本，保留原记录与审计依据。
    verification.status = "confirmed"
    db.commit()
    return {"id": verification.id, "status": verification.status, "suggested_text": verification.suggested_text}


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
    lecture = _manageable_lecture(db, lecture_id, user)

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
    # 级联删除: 简报 → 收藏 → 转录 → 课堂
    db.query(LectureBriefing).filter(LectureBriefing.lecture_id == lecture_id).delete()
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
    if lecture.course_id:
        lecture.title = req.title
    else:
        # 临时课堂没有课程实体，沿用旧行为修改其课程名称。
        lecture.course_name = req.title
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


def _translate_with_context_threadsafe(lecture_id: int, user_id: int,
                                       source_text: str, source_lang: str,
                                       target_lang: str) -> dict:
    """在线程池里用独立 session 取上下文并翻译，避免跨线程复用请求 session。"""
    db = SessionLocal()
    try:
        context = get_recent_source_sentences(db, lecture_id, user_id)
    finally:
        db.close()
    return translate_with_context(source_text, context, source_lang, target_lang)


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
    lecture = _manageable_lecture(db, lecture_id, user)
    if lecture.status not in {"recording", "paused"}:
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
    if lecture.translation_enabled:
        translation = await run_in_threadpool(
            _translate_with_context_threadsafe,
            lecture_id, user.id, source_text, source_lang, target_lang,
        )
    else:
        translation = {
            "text": source_text,
            "success": True,
            "provider": "disabled",
            "warning": None,
            "context_applied": False,
        }
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
        context_applied=translation["context_applied"],
    )


@router.post("/{lecture_id}/transcribe")
def api_transcribe(lecture_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """演示模式: 无音频时返回预设句子"""
    if not user:
        raise HTTPException(401, "请先登录")
    if IS_PRODUCTION:
        raise HTTPException(503, "生产环境未启用演示转录")
    _manageable_lecture(db, lecture_id, user)
    result = transcribe_audio(db, lecture_id, user.id, allow_demo=True)
    if not result:
        raise HTTPException(404, "课堂不存在或已结束")
    if result.get("done"):
        return {}
    return TranscriptionResp(**result)


@router.get("/{lecture_id}/transcriptions", response_model=list[TranscriptionResp])
def api_transcriptions(lecture_id: int, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db),
                       limit: int = Query(400, ge=1, le=400)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = _readable_lecture(db, lecture_id, user)
    items = get_transcriptions(db, lecture_id, user.id, limit=limit)
    from models.lecture import Bookmark
    bookmarked_ids = [t.id for t in items if t.is_bookmarked]
    bookmark_tags = {}
    if bookmarked_ids:
        bookmark_tags = dict(db.query(
            Bookmark.transcription_id, Bookmark.tag
        ).filter(
            Bookmark.user_id == lecture.user_id,
            Bookmark.transcription_id.in_(bookmarked_ids),
        ).all())
    result = []
    for t in items:
        d = TranscriptionResp.model_validate(t)
        d.bookmark_tag = bookmark_tags.get(t.id)
        result.append(d)
    return result


def _missing_briefing(lecture_id: int) -> BriefingResp:
    return BriefingResp(lecture_id=lecture_id, status="missing", edit_status="auto")


@router.get("/{lecture_id}/briefing", response_model=BriefingResp)
def api_get_briefing(lecture_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = _readable_lecture(db, lecture_id, user)
    row = get_briefing(db, lecture_id, lecture.user_id)
    if not row:
        return _missing_briefing(lecture_id)
    return BriefingResp(**briefing_to_dict(row))


@router.patch("/{lecture_id}/briefing", response_model=BriefingResp)
def api_patch_briefing(lecture_id: int, req: BriefingPatchReq,
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = _manageable_lecture(db, lecture_id, user)
    updates = req.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(422, "没有可保存的修订内容")
    try:
        row = patch_briefing(db, lecture_id, user.id, updates)
    except LookupError:
        raise HTTPException(404, "简报不存在") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None
    return BriefingResp(**briefing_to_dict(row))


@router.post("/{lecture_id}/briefing/assignments/{index}/confirm", response_model=BriefingResp)
def api_confirm_briefing_assignment(lecture_id: int, index: int,
                                    user: User = Depends(get_current_user),
                                    db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    if index < 0:
        raise HTTPException(422, "作业索引无效")
    _manageable_lecture(db, lecture_id, user)
    try:
        row = confirm_briefing_assignment(db, lecture_id, user.id, index)
    except LookupError:
        raise HTTPException(404, "简报不存在") from None
    except IndexError:
        raise HTTPException(404, "作业项不存在") from None
    return BriefingResp(**briefing_to_dict(row))


@router.delete("/{lecture_id}/briefing/assignments/{index}", response_model=BriefingResp)
def api_delete_briefing_assignment(lecture_id: int, index: int,
                                   user: User = Depends(get_current_user),
                                   db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    if index < 0:
        raise HTTPException(422, "作业索引无效")
    _manageable_lecture(db, lecture_id, user)
    try:
        row = delete_briefing_assignment(db, lecture_id, user.id, index)
    except LookupError:
        raise HTTPException(404, "简报不存在") from None
    except IndexError:
        raise HTTPException(404, "作业项不存在") from None
    return BriefingResp(**briefing_to_dict(row))


@router.post("/{lecture_id}/briefing", response_model=BriefingResp)
async def api_generate_briefing(lecture_id: int, background_tasks: BackgroundTasks,
                                req: GenerateBriefingReq | None = None,
                                user: User = Depends(get_current_user),
                                db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = _manageable_lecture(db, lecture_id, user)
    force = bool(req.force) if req else False
    confirm_overwrite = bool(req.confirm_overwrite) if req else False
    existing = get_briefing(db, lecture_id, user.id)
    if existing and existing.status == "ready" and not force:
        return BriefingResp(**briefing_to_dict(existing))
    if existing and existing.status == "generating" and not force:
        return BriefingResp(**briefing_to_dict(existing))
    if (
        force
        and existing
        and (getattr(existing, "edit_status", None) or "auto") == "edited"
        and not confirm_overwrite
    ):
        raise HTTPException(409, "简报已人工修订，重新生成将覆盖修改，请确认后重试")

    # 生成可能调用外部模型，放到后台，立即返回 generating 供前端轮询。
    background_tasks.add_task(_generate_briefing_job, lecture_id, user.id, force)
    return BriefingResp(lecture_id=lecture_id, status="generating", edit_status="auto")


def _remove_local_attachment(url: Optional[str]) -> None:
    if not url or not url.startswith("/uploads/attachments/"):
        return
    candidate = (ATTACHMENT_DIR / Path(url).name).resolve()
    if candidate.parent == ATTACHMENT_DIR.resolve():
        candidate.unlink(missing_ok=True)


@router.post("/{lecture_id}/briefing/items", response_model=BriefingResp)
def api_supplement_briefing_item(lecture_id: int, req: BriefingSupplementReq,
                                 user: User = Depends(get_current_user),
                                 db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = _manageable_lecture(db, lecture_id, user)
    if req.attachment_id and not get_attachment(db, lecture_id, user.id, req.attachment_id):
        raise HTTPException(422, "关联附件不存在")
    source = "from_attachment" if req.attachment_id else "user_added"
    try:
        row = supplement_briefing_item(
            db, lecture_id, user.id,
            section=req.section,
            text=req.text,
            sentence_order=req.sentence_order,
            due_date=req.due_date,
            attachment_id=req.attachment_id,
            needs_confirmation=req.needs_confirmation,
            source=source,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None
    return BriefingResp(**briefing_to_dict(row))


@router.get("/{lecture_id}/attachments", response_model=list[LectureAttachmentResp])
def api_list_attachments(lecture_id: int, category: Optional[str] = Query(None),
                         user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = _readable_lecture(db, lecture_id, user)
    if category and category not in {"assignment", "exam", "notice", "other"}:
        raise HTTPException(422, "不支持的附件类别")
    rows = list_attachments(db, lecture_id, lecture.user_id, category=category)
    return [LectureAttachmentResp(**attachment_to_dict(row)) for row in rows]


@router.post("/{lecture_id}/attachments", response_model=LectureAttachmentResp, status_code=201)
async def api_upload_attachment(lecture_id: int,
                                file: UploadFile = File(...),
                                category: str = Form("other"),
                                title: str = Form(""),
                                create_item: bool = Form(False),
                                item_text: str = Form(""),
                                user: User = Depends(get_current_user),
                                db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = _manageable_lecture(db, lecture_id, user)
    if category not in ATTACHMENT_CATEGORIES:
        raise HTTPException(422, "不支持的附件类别")

    header = await file.read(16)
    await file.seek(0)
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    ext = extension_for_upload(content_type, header, file.filename)
    if not ext:
        raise HTTPException(415, "仅支持 JPG / PNG / WEBP / PDF / PPT / PPTX")

    ensure_attachment_table()
    filename = f"L{lecture_id}_{uuid.uuid4().hex}{ext}"
    destination = ATTACHMENT_DIR / filename
    limit_mb = max_upload_mb_for(category, content_type, ext)
    written = 0
    try:
        with destination.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit_mb * 1024 * 1024:
                    raise HTTPException(413, f"附件不能超过 {limit_mb}MB")
                output.write(chunk)
        display_title = (title or file.filename or "课堂附件").strip()[:256] or "课堂附件"
        row = create_attachment(
            db,
            lecture_id=lecture_id,
            user_id=user.id,
            category=category,
            title=display_title,
            url=f"/uploads/attachments/{filename}",
            content_type=content_type or None,
            size_bytes=written,
        )
        if create_item:
            section = "assignments" if category in {"assignment", "notice"} else (
                "exam_hints" if category == "exam" else "key_points"
            )
            text = (item_text or display_title).strip()
            if text:
                supplement_briefing_item(
                    db, lecture_id, user.id,
                    section=section,
                    text=text,
                    attachment_id=row.id,
                    needs_confirmation=False,
                    source="from_attachment",
                )
        return LectureAttachmentResp(**attachment_to_dict(row))
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except Exception:
        destination.unlink(missing_ok=True)
        raise


@router.get("/{lecture_id}/briefing/export")
def api_export_briefing(lecture_id: int, format: str = Query("md"),
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = _readable_lecture(db, lecture_id, user)
    if (format or "md").lower() != "md":
        raise HTTPException(422, "当前仅支持 format=md")
    markdown = build_briefing_markdown(db, lecture, lecture.user_id)
    title = lecture.title or lecture.course_name or f"lecture-{lecture_id}"
    filename = f"{title}-简报.md".replace("/", "_")
    return Response(
        content=markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": content_disposition(filename)},
    )


@router.get("/{lecture_id}/materials/export")
def api_export_materials(lecture_id: int, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    lecture = _readable_lecture(db, lecture_id, user)
    payload = build_materials_zip(db, lecture, lecture.user_id)
    title = lecture.title or lecture.course_name or f"lecture-{lecture_id}"
    filename = f"{title}-资料包.zip".replace("/", "_")
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": content_disposition(filename)},
    )


@router.delete("/{lecture_id}/attachments/{attachment_id}", status_code=204)
def api_delete_attachment(lecture_id: int, attachment_id: int,
                          user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    _manageable_lecture(db, lecture_id, user)
    url = delete_attachment(db, lecture_id, user.id, attachment_id)
    if url is None:
        raise HTTPException(404, "附件不存在")
    _remove_local_attachment(url)
    return Response(status_code=204)


@router.post("/{lecture_id}/assistant/ask", response_model=AssistantAskResp)
def api_assistant_ask(lecture_id: int, req: AssistantAskReq,
                      user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(401, "请先登录")
    # P0: 公开课跨用户助手留到下一阶段，写/问答仍仅课主。
    lecture = _manageable_lecture(db, lecture_id, user)
    try:
        result = answer_lecture_question(
            db,
            lecture_id,
            user.id,
            req.question,
            [item.model_dump() for item in req.history],
            lecture.course_name,
        )
    except QuotaExceededError as exc:
        raise HTTPException(429, str(exc)) from exc
    if not result:
        raise HTTPException(404, "课堂不存在")
    return AssistantAskResp(**result)

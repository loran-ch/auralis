"""LiveTrans Voice — 课堂录音 + 转录服务"""
import random
from datetime import datetime
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from config import ASR_CONTEXT_SENTENCES
from models.lecture import Lecture, Transcription

def _now():
    """返回本地时间"""
    return datetime.now()


# ─── 演示用 ASR 数据 (英文→中文，课堂场景) ──────────────
_DEMO_SENTENCES = [
    "Today we will discuss the fundamentals of thermodynamics.",
    "Thermodynamics deals with the conversion of energy into work.",
    "The first law of thermodynamics states that energy cannot be created or destroyed.",
    "This is a fundamental principle that will definitely be on the exam.",
    "Let us now consider a simple example: a piston in a cylinder.",
    "The formula for this is W equals P times delta V.",
    "Please remember this formula, it is very important for the final.",
    "The efficiency of a heat engine is defined as the ratio of useful work to input heat.",
    "Now let us move on to the second law of thermodynamics.",
    "The entropy of an isolated system never decreases.",
]


# ─── 课堂管理 ────────────────────────────────────────────

def start_lecture(db: Session, user_id: int, course_name: str,
                  source_lang: str, target_lang: str) -> Lecture:
    """开始一堂新课"""
    lecture = Lecture(
        user_id=user_id, course_name=course_name,
        source_lang=source_lang, target_lang=target_lang,
        status="recording", lecture_date=_now().date(),
        started_at=_now(),
    )
    db.add(lecture)
    db.commit()
    db.refresh(lecture)
    return lecture


def stop_lecture(db: Session, lecture_id: int, user_id: int) -> Optional[Lecture]:
    """停止录音，结束课堂"""
    lecture = db.query(Lecture).filter(
        Lecture.id == lecture_id, Lecture.user_id == user_id
    ).first()
    if not lecture:
        return None
    if lecture.status == "completed":
        return lecture
    lecture.status = "completed"
    lecture.ended_at = _now()
    # 更新统计数据
    lecture.sentence_count = db.query(Transcription).filter(
        Transcription.lecture_id == lecture_id
    ).count()
    lecture.bookmark_count = db.query(Transcription).filter(
        Transcription.lecture_id == lecture_id,
        Transcription.is_bookmarked == True,
    ).count()
    if lecture.started_at and lecture.ended_at:
        lecture.duration_seconds = int(
            (lecture.ended_at - lecture.started_at).total_seconds()
        )
    db.commit()
    db.refresh(lecture)
    return lecture


def begin_lecture_session(db: Session, user_id: int, course_name: str,
                          source_lang: str, target_lang: str) -> tuple[Lecture, bool, Optional[Lecture]]:
    """开始或恢复课堂。

    若当前有已暂停的课堂，恢复同一堂课（保留已有字幕）。
    若有仍在录制中的课堂，先结束再开新课。
    返回 (当前课堂, 是否恢复暂停课, 被结束的旧课堂)。
    """
    active = get_active_lecture(db, user_id)
    if active and active.status == "paused":
        lecture = resume_lecture(db, active.id, user_id) or active
        return lecture, True, None
    stopped = None
    if active:
        stopped = stop_lecture(db, active.id, user_id)
    lecture = start_lecture(db, user_id, course_name, source_lang, target_lang)
    return lecture, False, stopped


def get_active_lecture(db: Session, user_id: int) -> Optional[Lecture]:
    return db.query(Lecture).filter(
        Lecture.user_id == user_id,
        Lecture.status.in_(("recording", "paused")),
    ).order_by(desc(Lecture.started_at)).first()


def pause_lecture(db: Session, lecture_id: int, user_id: int) -> Optional[Lecture]:
    lecture = db.query(Lecture).filter(
        Lecture.id == lecture_id,
        Lecture.user_id == user_id,
        Lecture.status == "recording",
    ).first()
    if not lecture:
        return None
    lecture.status = "paused"
    db.commit()
    db.refresh(lecture)
    return lecture


def resume_lecture(db: Session, lecture_id: int, user_id: int) -> Optional[Lecture]:
    lecture = db.query(Lecture).filter(
        Lecture.id == lecture_id,
        Lecture.user_id == user_id,
        Lecture.status == "paused",
    ).first()
    if not lecture:
        return None
    lecture.status = "recording"
    db.commit()
    db.refresh(lecture)
    return lecture


def get_lecture(db: Session, lecture_id: int, user_id: int) -> Optional[Lecture]:
    return db.query(Lecture).filter(
        Lecture.id == lecture_id,
        Lecture.user_id == user_id,
    ).first()


# ─── 转录 (演示模式) ──────────────────────────────────────

def transcribe_audio(db: Session, lecture_id: int, user_id: int,
                     source_text: str = None,
                     translated_text: str = None,
                     start_offset_ms: int | None = None,
                     end_offset_ms: int | None = None,
                     engine: str = "default") -> Optional[dict]:
    """
    保存转录句子。如果有前端传来的真实识别文本则使用，否则使用演示数据
    """
    # 锁定课堂行，确保多请求并发写入时 sentence_order 唯一且连续。
    lecture = db.query(Lecture).filter(
        Lecture.id == lecture_id, Lecture.user_id == user_id
    ).with_for_update().first()
    if not lecture or lecture.status not in ("recording", "paused"):
        return None

    count = int(lecture.sentence_count or 0)

    # 如果前端传来了真实识别文本，直接保存
    if source_text:
        src = source_text
        tgt = translated_text or source_text
    else:
        # 演示模式
        if count >= len(_DEMO_SENTENCES):
            src = "Thank you for your attention. Any questions?"
        else:
            src = _DEMO_SENTENCES[count]
        from services.translator import translate
        tgt = translate(src, lecture.source_lang, lecture.target_lang)

    offset = count * 8000 if start_offset_ms is None else max(0, start_offset_ms)
    end_offset = offset + 8000 if end_offset_ms is None else max(offset, end_offset_ms)

    transcription = Transcription(
        lecture_id=lecture_id, user_id=user_id,
        source_text=src, source_lang=lecture.source_lang,
        translated_text=tgt, target_lang=lecture.target_lang,
        sentence_order=count + 1,
        start_offset_ms=offset, end_offset_ms=end_offset,
        recorded_at=_now(),
        ocr_confidence=round(random.uniform(0.88, 0.98), 2),
        engine=engine,
    )
    db.add(transcription)
    lecture.sentence_count = count + 1
    db.commit()
    db.refresh(transcription)

    return {
        "id": transcription.id,
        "sentence_order": transcription.sentence_order,
        "source_text": transcription.source_text,
        "source_lang": transcription.source_lang,
        "translated_text": transcription.translated_text,
        "target_lang": transcription.target_lang,
        "is_bookmarked": transcription.is_bookmarked,
        "ocr_confidence": transcription.ocr_confidence,
        "engine": transcription.engine,
        "mode": transcription.mode,
        "start_offset_ms": transcription.start_offset_ms,
        "end_offset_ms": transcription.end_offset_ms,
        "recorded_at": transcription.recorded_at,
    }


def get_transcriptions(db: Session, lecture_id: int, user_id: int,
                       limit: int = 50) -> list:
    return db.query(Transcription).filter(
        Transcription.lecture_id == lecture_id,
        Transcription.user_id == user_id,
    ).order_by(Transcription.sentence_order).limit(limit).all()


def get_recent_source_sentences(db: Session, lecture_id: int, user_id: int,
                                limit: int | None = None) -> list[str]:
    """取最近 N 句原文作为翻译上下文（按句序从旧到新，不含当前句）。"""
    if limit is None:
        limit = ASR_CONTEXT_SENTENCES
    if limit <= 0:
        return []
    rows = db.query(Transcription.source_text).filter(
        Transcription.lecture_id == lecture_id,
        Transcription.user_id == user_id,
    ).order_by(Transcription.sentence_order.desc()).limit(limit).all()
    return [row[0] for row in reversed(rows) if row[0]]

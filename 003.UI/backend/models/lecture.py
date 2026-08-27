"""LiveTrans Voice — 课堂 + 转录 + 收藏模型"""
from datetime import datetime
from sqlalchemy import (Column, BigInteger, String, Integer, Text, Date, DateTime,
                        Enum, Boolean, Float, JSON, ForeignKey, Index,
                        UniqueConstraint)
from sqlalchemy.dialects.mysql import BIGINT as MYSQL_BIGINT
from database import Base


class Lecture(Base):
    __tablename__ = "lectures"
    __table_args__ = (
        Index("idx_user_status_date", "user_id", "status", "lecture_date"),
        Index("idx_lecture_course_date", "course_id", "lecture_date"),
        UniqueConstraint("course_id", "session_number", name="uk_course_session_number"),
    )

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id          = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id         = Column(BigInteger, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    session_number    = Column(Integer, nullable=True)
    course_name      = Column(String(256), nullable=False)
    title            = Column(String(256))
    source_lang      = Column(String(5), nullable=False)
    target_lang      = Column(String(5), nullable=False)
    translation_enabled = Column(Boolean, default=True, nullable=False)
    duration_seconds = Column(Integer, default=0)
    sentence_count   = Column(Integer, default=0)
    bookmark_count   = Column(Integer, default=0)
    audio_url        = Column(String(512))
    audio_size_bytes = Column(BigInteger)
    location_name    = Column(String(256))
    room             = Column(String(64))
    subject_tags     = Column(JSON)
    status           = Column(Enum("recording", "paused", "completed", "failed"), default="completed")
    exported         = Column(Boolean, default=False)
    lecture_date     = Column(Date, default=lambda: datetime.now().date())
    started_at       = Column(DateTime)
    ended_at         = Column(DateTime)
    created_at       = Column(DateTime, default=datetime.now)
    updated_at       = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Transcription(Base):
    __tablename__ = "transcriptions"
    __table_args__ = (
        UniqueConstraint("lecture_id", "sentence_order", name="uk_lecture_sentence_order"),
    )

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    lecture_id       = Column(BigInteger, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    user_id          = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_text      = Column(Text, nullable=False)
    source_lang      = Column(String(5), nullable=False)
    ocr_confidence   = Column(Float)
    translated_text  = Column(Text, nullable=False)
    target_lang      = Column(String(5), nullable=False)
    engine           = Column(String(32), default="default")
    mode             = Column(Enum("online", "offline"), default="online")
    sentence_order   = Column(Integer, nullable=False)
    start_offset_ms  = Column(Integer, default=0)
    end_offset_ms    = Column(Integer)
    recorded_at      = Column(DateTime, nullable=False)
    is_bookmarked    = Column(Boolean, default=False)
    created_at       = Column(DateTime, default=datetime.now)


class LectureBriefing(Base):
    __tablename__ = "lecture_briefings"
    __table_args__ = (
        UniqueConstraint("lecture_id", name="uk_lecture_briefing"),
        Index("idx_briefing_user", "user_id"),
    )

    id                     = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    lecture_id             = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    user_id                = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status                 = Column(Enum("generating", "ready", "failed", "empty"), default="generating")
    edit_status            = Column(Enum("auto", "edited"), default="auto", nullable=False)
    provider               = Column(String(64))
    overview               = Column(Text)
    outline                = Column(JSON)
    key_points             = Column(JSON)
    exam_hints             = Column(JSON)
    questions              = Column(JSON)
    terms                  = Column(JSON)
    assignments            = Column(JSON)
    source_sentence_count  = Column(Integer, default=0)
    error_message          = Column(String(512))
    previous_payload       = Column(JSON)
    generated_at           = Column(DateTime)
    edited_at              = Column(DateTime)
    created_at             = Column(DateTime, default=datetime.now)
    updated_at             = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id          = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    transcription_id = Column(BigInteger, ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False)
    lecture_id       = Column(BigInteger, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    tag              = Column(Enum("important", "question", "exam", "definition"), nullable=False)
    note             = Column(Text)
    created_at       = Column(DateTime, default=datetime.now)


class AssistantThread(Base):
    """学习助手会话；lecture_ids 为空时表示查询整门课程。"""
    __tablename__ = "assistant_threads"
    __table_args__ = (
        Index("idx_assistant_thread_user_updated", "user_id", "updated_at"),
        Index("idx_assistant_thread_course", "course_id", "updated_at"),
    )

    id               = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id          = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id        = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    lecture_ids      = Column(JSON, nullable=False)
    title            = Column(String(256), nullable=False, default="新学习会话")
    summary          = Column(Text)
    created_at       = Column(DateTime, default=datetime.now)
    updated_at       = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class AssistantMessage(Base):
    """会话内的一轮提问或回答；引用单独随回答持久化以便可追溯。"""
    __tablename__ = "assistant_messages"
    __table_args__ = (
        Index("idx_assistant_message_thread_created", "thread_id", "created_at", "id"),
    )

    id               = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    thread_id        = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("assistant_threads.id", ondelete="CASCADE"), nullable=False)
    user_id          = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role             = Column(Enum("user", "assistant"), nullable=False)
    content          = Column(Text, nullable=False)
    citations        = Column(JSON)
    created_at       = Column(DateTime, default=datetime.now)


class MediaAsset(Base):
    """课堂媒体原件和关键帧。视频可缺失，不能影响录音课堂。"""
    __tablename__ = "media_assets"
    __table_args__ = (
        Index("idx_media_asset_lecture_type", "lecture_id", "media_type", "start_offset_ms"),
        Index("idx_media_asset_user_created", "user_id", "created_at"),
    )

    id              = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    lecture_id      = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    user_id         = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    media_type      = Column(Enum("video", "frame", "clip"), nullable=False)
    status          = Column(Enum("uploaded", "ready", "processing", "unavailable", "failed"), nullable=False, default="uploaded")
    url             = Column(String(512), nullable=False)
    content_type    = Column(String(128))
    size_bytes      = Column(BigInteger)
    start_offset_ms = Column(Integer, default=0)
    end_offset_ms   = Column(Integer)
    metadata_json   = Column(JSON)
    error_message   = Column(String(512))
    created_at      = Column(DateTime, default=datetime.now)
    updated_at      = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class MediaClipCandidate(Base):
    """AI/规则生成的片段时间轴；真正导出仅在用户确认后进行。"""
    __tablename__ = "media_clip_candidates"
    __table_args__ = (Index("idx_clip_candidate_lecture", "lecture_id", "score"),)

    id              = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    lecture_id      = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    user_id         = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title           = Column(String(256), nullable=False)
    reason          = Column(String(512))
    start_offset_ms = Column(Integer, nullable=False)
    end_offset_ms   = Column(Integer, nullable=False)
    score           = Column(Float, nullable=False, default=0)
    status          = Column(Enum("candidate", "exporting", "ready", "unavailable", "failed"), nullable=False, default="candidate")
    media_url       = Column(String(512))
    error_message   = Column(String(512))
    created_at      = Column(DateTime, default=datetime.now)


class LectureAttachment(Base):
    """人工上传的作业截图、考点板书、通知 PDF 等课堂附件。"""
    __tablename__ = "lecture_attachments"
    __table_args__ = (
        Index("idx_lecture_attachment_lecture", "lecture_id", "category", "created_at"),
        Index("idx_lecture_attachment_user", "user_id", "created_at"),
    )

    id            = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    lecture_id    = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    user_id       = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category      = Column(Enum("assignment", "exam", "notice", "other", "material"), nullable=False, default="other")
    title         = Column(String(256), nullable=False)
    url           = Column(String(512), nullable=False)
    content_type  = Column(String(128))
    size_bytes    = Column(BigInteger)
    status        = Column(Enum("ready", "failed"), nullable=False, default="ready")
    error_message = Column(String(512))
    created_at    = Column(DateTime, default=datetime.now)
    updated_at    = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class TranscriptionVerification(Base):
    """二次核验不覆盖原转录，任何建议均需要用户确认。"""
    __tablename__ = "transcription_verifications"
    __table_args__ = (
        Index("idx_verification_transcription", "transcription_id", "created_at"),
        Index("idx_verification_lecture", "lecture_id", "status"),
    )

    id               = Column(MYSQL_BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    lecture_id       = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False)
    transcription_id = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False)
    user_id          = Column(MYSQL_BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status           = Column(Enum("processing", "suggested", "confirmed", "unchanged", "unavailable", "failed"), nullable=False, default="processing")
    original_text    = Column(Text, nullable=False)
    suggested_text   = Column(Text)
    secondary_asr    = Column(Text)
    evidence_json    = Column(JSON)
    error_message    = Column(String(512))
    created_at       = Column(DateTime, default=datetime.now)
    updated_at       = Column(DateTime, default=datetime.now, onupdate=datetime.now)

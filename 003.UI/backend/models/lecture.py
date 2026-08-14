"""LiveTrans Voice — 课堂 + 转录 + 收藏模型"""
from datetime import datetime
from sqlalchemy import (Column, BigInteger, String, Integer, Text, Date, DateTime,
                        Enum, Boolean, Float, JSON, ForeignKey, Index,
                        UniqueConstraint)
from sqlalchemy.dialects.mysql import BIGINT as MYSQL_BIGINT
from database import Base


class Lecture(Base):
    __tablename__ = "lectures"
    __table_args__ = (Index("idx_user_status_date", "user_id", "status", "lecture_date"),)

    id               = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id          = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_name      = Column(String(256), nullable=False)
    source_lang      = Column(String(5), nullable=False)
    target_lang      = Column(String(5), nullable=False)
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
    provider               = Column(String(64))
    overview               = Column(Text)
    outline                = Column(JSON)
    key_points             = Column(JSON)
    exam_hints             = Column(JSON)
    questions              = Column(JSON)
    terms                  = Column(JSON)
    source_sentence_count  = Column(Integer, default=0)
    error_message          = Column(String(512))
    generated_at           = Column(DateTime)
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

"""LiveTrans Voice — 用户偏好、语言、统计与课程表模型。"""
from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, Enum, ForeignKey,
                        Integer, SmallInteger, String, Time)

from database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    default_source_lang = Column(String(5), default="auto")
    default_target_lang = Column(String(5), default="zh-CN")
    default_engine = Column(String(32), default="default")
    translation_mode = Column(Enum("online", "offline", "auto"), default="auto")
    font_size = Column(Enum("small", "medium", "large"), default="medium")
    dark_mode = Column(Enum("system", "light", "dark"), default="system")
    flash_mode = Column(Enum("auto", "on", "off"), default="auto")
    ocr_frequency = Column(Enum("high", "medium", "low"), default="medium")
    history_auto_clean = Column(Boolean, default=True)
    history_keep_count = Column(Integer, default=500)
    cloud_sync_enabled = Column(Boolean, default=False)
    sync_history = Column(Boolean, default=True)
    sync_bookmarks = Column(Boolean, default=True)
    sync_settings = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Language(Base):
    __tablename__ = "languages"

    code = Column(String(5), primary_key=True)
    name_native = Column(String(64), nullable=False)
    name_en = Column(String(64), nullable=False)
    flag_emoji = Column(String(8))
    region = Column(String(32))
    supports_offline = Column(Boolean, default=False)
    offline_size_mb = Column(Integer)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)


class UserStats(Base):
    __tablename__ = "user_stats"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    weekly_record_seconds = Column(Integer, default=0)
    total_bookmark_count = Column(Integer, default=0)
    total_lecture_count = Column(Integer, default=0)
    total_record_seconds = Column(Integer, default=0)
    current_streak_days = Column(Integer, default=0)
    weekly_bookmark_count = Column(Integer, default=0)
    exam_mastery_improve = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CourseSchedule(Base):
    __tablename__ = "course_schedule"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_name = Column(String(256), nullable=False)
    source_lang = Column(String(5), nullable=False)
    target_lang = Column(String(5), nullable=False)
    day_of_week = Column(SmallInteger, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    room = Column(String(64))
    professor_name = Column(String(128))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

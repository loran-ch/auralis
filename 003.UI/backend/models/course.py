"""课程中心模型：课程是课程系列，Lecture 是每一次实际上课记录。"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, String

from database import Base


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        Index("idx_course_user_active", "user_id", "is_active", "updated_at"),
        Index("idx_course_public_active", "is_public", "is_active", "updated_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(256), nullable=False)
    professor_name = Column(String(128))
    room = Column(String(64))
    term = Column(String(64))
    source_lang = Column(String(5), nullable=False, default="en")
    target_lang = Column(String(5), nullable=False, default="zh-CN")
    translation_enabled = Column(Boolean, nullable=False, default=False)
    color = Column(String(16), nullable=False, default="#2563EB")
    is_active = Column(Boolean, nullable=False, default=True)
    is_public = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

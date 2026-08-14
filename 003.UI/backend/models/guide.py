"""LiveTrans Voice — 前台功能说明（管理员可编辑）"""
from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, DateTime, JSON
from database import Base


class AppGuide(Base):
    __tablename__ = "app_guides"

    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    slug            = Column(String(64), unique=True, nullable=False, comment="说明标识，如 recorder_features")
    title           = Column(String(128), nullable=False)
    subtitle        = Column(String(512))
    items           = Column(JSON, comment="[{icon, title, body}]")
    footer_hint     = Column(String(256))
    updated_by_name = Column(String(64))
    created_at      = Column(DateTime, default=datetime.now)
    updated_at      = Column(DateTime, default=datetime.now, onupdate=datetime.now)

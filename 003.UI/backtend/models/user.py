"""
LiveTrans — 数据模型 (对应 004.数据库脚本/01_建表脚本.sql)
"""
from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, String, Integer, Text, DateTime, Enum,
    Boolean, Float, JSON, ForeignKey, Index,
)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    """用户表 — PRD §4.7.2 & §4.7.8"""
    __tablename__ = "users"

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    nickname       = Column(String(64), nullable=True)
    avatar_url     = Column(String(512), nullable=True)
    email          = Column(String(128), nullable=True, unique=True)
    email_verified = Column(Boolean, default=False)
    phone          = Column(String(20), nullable=True, unique=True)
    phone_verified = Column(Boolean, default=False)
    password_hash  = Column(String(256), nullable=True)
    status         = Column(Enum("active", "disabled", "deleting", "deleted"), default="active")

    wechat_openid  = Column(String(128), nullable=True, unique=True)
    apple_user_id  = Column(String(256), nullable=True, unique=True)
    google_openid  = Column(String(128), nullable=True, unique=True)

    member_level   = Column(Enum("free", "pro"), default="free")
    member_since   = Column(DateTime, nullable=True)

    deleted_at     = Column(DateTime, nullable=True)
    last_login_at  = Column(DateTime, nullable=True)
    last_login_ip  = Column(String(45), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VerificationCode(Base):
    """验证码表 — PRD §4.7.2"""
    __tablename__ = "verification_codes"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    target      = Column(String(128), nullable=False)
    target_type = Column(Enum("phone", "email"), nullable=False)
    code        = Column(String(6), nullable=False)
    scene       = Column(Enum("register", "login", "reset_password", "bind", "unbind", "delete_account"),
                         default="register")
    ip_address  = Column(String(45), nullable=True)
    expires_at  = Column(DateTime, nullable=False)
    used        = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)


class UserToken(Base):
    """用户令牌表 — PRD §4.7.3"""
    __tablename__ = "user_tokens"

    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id         = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    access_token    = Column(String(512), nullable=False)
    refresh_token   = Column(String(512), nullable=False)
    device_info     = Column(String(256), nullable=True)
    device_id       = Column(String(128), nullable=True)
    ip_address      = Column(String(45), nullable=True)
    access_expires  = Column(DateTime, nullable=False)
    refresh_expires = Column(DateTime, nullable=False)
    revoked         = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=datetime.utcnow)


class UserDevice(Base):
    """用户设备表 — PRD §4.7.7"""
    __tablename__ = "user_devices"

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id        = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id      = Column(String(128), nullable=False)
    device_name    = Column(String(128), nullable=True)
    device_os      = Column(String(64), nullable=True)
    os_version     = Column(String(32), nullable=True)
    app_version    = Column(String(16), nullable=True)
    last_active_at = Column(DateTime, default=datetime.utcnow)
    is_trusted     = Column(Boolean, default=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

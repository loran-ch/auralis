"""LiveTrans Voice — 用户相关模型"""
from datetime import datetime
from sqlalchemy import (Column, BigInteger, String, Integer, Text, DateTime,
                        Enum, Boolean, Float, JSON, ForeignKey, Index)
from database import Base


class User(Base):
    __tablename__ = "users"

    id             = Column(BigInteger, primary_key=True, autoincrement=True)
    nickname       = Column(String(64), nullable=False)
    avatar_url     = Column(String(512))
    email          = Column(String(128), unique=True)
    email_verified = Column(Boolean, default=False)
    phone          = Column(String(20), unique=True)
    phone_verified = Column(Boolean, default=False)
    password_hash  = Column(String(256))
    status         = Column(Enum("active", "disabled", "deleting", "deleted"), default="active")
    wechat_openid  = Column(String(128), unique=True)
    apple_user_id  = Column(String(256), unique=True)
    google_openid  = Column(String(128), unique=True)
    member_level   = Column(Enum("free", "premium"), default="free")
    university     = Column(String(256))
    major          = Column(String(256))
    focus_area     = Column(String(256))
    last_login_at  = Column(DateTime)
    last_login_ip  = Column(String(45))
    deleted_at     = Column(DateTime)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    target      = Column(String(128), nullable=False)
    target_type = Column(Enum("phone", "email"), nullable=False)
    code        = Column(String(6), nullable=False)
    scene       = Column(Enum("register", "login", "reset_password", "bind", "delete_account"), default="register")
    ip_address  = Column(String(45))
    expires_at  = Column(DateTime, nullable=False)
    used        = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)


class UserToken(Base):
    __tablename__ = "user_tokens"

    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id         = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    access_token    = Column(String(512), nullable=False)
    refresh_token   = Column(String(512), nullable=False)
    device_info     = Column(String(256))
    device_id       = Column(String(128))
    ip_address      = Column(String(45))
    access_expires  = Column(DateTime, nullable=False)
    refresh_expires = Column(DateTime, nullable=False)
    revoked         = Column(Boolean, default=False)
    created_at      = Column(DateTime, default=datetime.utcnow)

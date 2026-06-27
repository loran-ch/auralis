"""
LiveTrans — 安全工具: JWT 编解码 & 密码哈希
PRD §4.7.3 Token管理 & §7.4 安全性 (bcrypt ≥12轮)
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import jwt, JWTError

from config import (
    JWT_SECRET, JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_DAYS, REFRESH_TOKEN_EXPIRE_DAYS,
)


def hash_password(password: str) -> str:
    """bcrypt 哈希 — 12 轮 (PRD §7.4)"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int) -> tuple[str, datetime]:
    """生成 Access Token (7天)"""
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "access", "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), expire


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    """生成 Refresh Token (30天)"""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), expire


def create_token_pair(user_id: int) -> dict:
    """生成 Access + Refresh Token 对"""
    access, access_exp = create_access_token(user_id)
    refresh, refresh_exp = create_refresh_token(user_id)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "access_expires": access_exp,
        "refresh_expires": refresh_exp,
    }


def decode_token(token: str) -> Optional[dict]:
    """解码 JWT Token，失败返回 None"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """从 Token 中提取 user_id"""
    payload = decode_token(token)
    if payload and payload.get("type") == "access":
        return int(payload.get("sub"))
    return None

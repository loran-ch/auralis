"""LiveTrans Voice — JWT + bcrypt"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import jwt, JWTError
from config import JWT_SECRET, JWT_ALGORITHM, ACCESS_EXPIRE_DAYS, REFRESH_EXPIRE_DAYS


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: int) -> tuple[str, datetime]:
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "access", "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), expire


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), expire


def create_token_pair(user_id: int) -> dict:
    access, a_exp = create_access_token(user_id)
    refresh, r_exp = create_refresh_token(user_id)
    return {"access_token": access, "refresh_token": refresh,
            "access_expires": a_exp, "refresh_expires": r_exp}


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    payload = decode_token(token)
    if payload and payload.get("type") == "access":
        return int(payload.get("sub"))
    return None

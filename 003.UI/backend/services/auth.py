"""LiveTrans Voice — 认证业务逻辑"""
import random
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from models.user import User, VerificationCode, UserToken
from utils.security import hash_password, verify_password, create_token_pair
from config import (CODE_LENGTH, CODE_EXPIRE_SEC, CODE_RESEND_SEC,
                    CODE_DAILY_LIMIT)


def _gen_code() -> str:
    return "".join([str(random.randint(0, 9)) for _ in range(CODE_LENGTH)])


# ─── 验证码 ─────────────────────────────────────────────

def send_code(db: Session, target: str, scene: str, ip: Optional[str]) -> dict:
    now = datetime.now(timezone.utc)

    # 60秒限流
    recent = db.query(VerificationCode).filter(
        VerificationCode.target == target,
        VerificationCode.created_at >= now - timedelta(seconds=CODE_RESEND_SEC),
    ).first()
    if recent:
        wait = CODE_RESEND_SEC - int((now - recent.created_at.replace(tzinfo=timezone.utc)).total_seconds())
        return {"success": False, "message": f"请 {max(1, wait)} 秒后重试"}

    # 每日上限
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.query(VerificationCode).filter(
        VerificationCode.target == target,
        VerificationCode.created_at >= today,
    ).count()
    if count >= CODE_DAILY_LIMIT:
        return {"success": False, "message": "今日验证码次数已用完"}

    code = _gen_code()
    expires = now + timedelta(seconds=CODE_EXPIRE_SEC)
    vc = VerificationCode(target=target, target_type="phone", code=code,
                          scene=scene, ip_address=ip, expires_at=expires)
    db.add(vc)
    db.commit()

    # 开发环境打印验证码
    print(f"\n  [LiveTrans Voice] 验证码: {code} → {target} ({scene})\n")
    return {"success": True, "message": "验证码已发送", "expires_in": CODE_EXPIRE_SEC}


def verify_code(db: Session, target: str, code: str, scene: str) -> bool:
    vc = db.query(VerificationCode).filter(
        VerificationCode.target == target,
        VerificationCode.code == code,
        VerificationCode.scene == scene,
        VerificationCode.used == False,
        VerificationCode.expires_at > datetime.now(timezone.utc),
    ).order_by(VerificationCode.created_at.desc()).first()
    if vc:
        vc.used = True
        db.commit()
        return True
    return False


# ─── 注册 ───────────────────────────────────────────────

def register(db: Session, phone: str, code: str, password: str,
             nickname: Optional[str], ip: Optional[str]) -> dict:
    if not verify_code(db, phone, code, "register"):
        return {"success": False, "message": "验证码错误或已过期"}

    if db.query(User).filter(User.phone == phone).first():
        return {"success": False, "message": "该手机号已注册"}

    user = User(
        nickname=nickname or f"用户_{phone[-4:]}",
        phone=phone, phone_verified=True,
        password_hash=hash_password(password),
        last_login_at=datetime.now(timezone.utc),
        last_login_ip=ip,
    )
    db.add(user)
    db.flush()

    tokens = create_token_pair(user.id)
    _save_token(db, user.id, tokens, "register", ip)
    db.commit()

    return {"success": True, "message": "注册成功", "user": user, "tokens": tokens}


# ─── 登录 ───────────────────────────────────────────────

def login(db: Session, phone: str, password: str, ip: Optional[str]) -> dict:
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        return {"success": False, "message": "手机号未注册"}
    if not user.password_hash:
        return {"success": False, "message": "账号异常，请联系客服"}
    if not verify_password(password, user.password_hash):
        return {"success": False, "message": "密码错误"}
    if user.status != "active":
        return {"success": False, "message": f"账户状态异常: {user.status}"}

    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = ip

    tokens = create_token_pair(user.id)
    _save_token(db, user.id, tokens, "login", ip)
    db.commit()

    return {"success": True, "message": "登录成功", "user": user, "tokens": tokens}


# ─── 令牌 ───────────────────────────────────────────────

def _save_token(db: Session, user_id: int, tokens: dict, device: str, ip: Optional[str]):
    db.add(UserToken(
        user_id=user_id, access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"], device_info=device,
        ip_address=ip, access_expires=tokens["access_expires"],
        refresh_expires=tokens["refresh_expires"],
    ))


def revoke_all_tokens(db: Session, user_id: int):
    db.query(UserToken).filter(
        UserToken.user_id == user_id,
        UserToken.revoked == False,
    ).update({"revoked": True})
    db.commit()

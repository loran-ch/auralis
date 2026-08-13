"""LiveTrans Voice — 认证业务逻辑"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from models.user import User, VerificationCode, UserToken
from models.preferences import UserSettings, UserStats
from utils.security import (hash_password, verify_password, create_token_pair,
                            get_user_id_from_token, get_refresh_user_id,
                            hash_token)
from config import (CODE_LENGTH, CODE_EXPIRE_SEC, CODE_RESEND_SEC,
                    CODE_DAILY_LIMIT, DEBUG)
from services.captcha import verify_registration_captcha


def _gen_code() -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(CODE_LENGTH))


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

    # 仅本地开发时输出；生产环境应在这里接入短信/邮件服务商。
    if DEBUG:
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

def register(db: Session, username: str, password: str, nickname: Optional[str],
             captcha_token: str, captcha_code: str, ip: Optional[str],
             phone: Optional[str] = None) -> dict:
    if not verify_registration_captcha(db, captcha_token, captcha_code):
        return {"success": False, "message": "验证码错误或已过期"}

    if db.query(User).filter(User.username == username).first():
        return {"success": False, "message": "该用户名已被使用"}
    if phone and db.query(User).filter(User.phone == phone).first():
        return {"success": False, "message": "该手机号已注册"}

    user = User(
        nickname=nickname or username,
        username=username,
        phone=phone, phone_verified=False,
        password_hash=hash_password(password),
        last_login_at=datetime.now(timezone.utc),
        last_login_ip=ip,
    )
    db.add(user)
    db.flush()
    db.add(UserSettings(user_id=user.id))
    db.add(UserStats(user_id=user.id))

    tokens = create_token_pair(user.id)
    _save_token(db, user.id, tokens, "register", ip)
    db.commit()

    return {"success": True, "message": "注册成功", "user": user, "tokens": tokens}


# ─── 登录 ───────────────────────────────────────────────

def login(db: Session, account: str, password: str, ip: Optional[str]) -> dict:
    user = db.query(User).filter(
        (User.username == account) | (User.phone == account)
    ).first()
    # 统一失败信息，避免通过接口枚举已注册账号。
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        return {"success": False, "message": "账号或密码错误"}
    if user.status != "active":
        return {"success": False, "message": "账号当前不可用"}

    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = ip

    # 清理已过期会话状态，避免令牌表无限保留“有效”标记。
    db.query(UserToken).filter(
        UserToken.user_id == user.id,
        UserToken.revoked == False,
        UserToken.refresh_expires <= datetime.now(timezone.utc),
    ).update({"revoked": True}, synchronize_session=False)

    tokens = create_token_pair(user.id)
    _save_token(db, user.id, tokens, "login", ip)
    db.commit()

    return {"success": True, "message": "登录成功", "user": user, "tokens": tokens}


# ─── 令牌 ───────────────────────────────────────────────

def _save_token(db: Session, user_id: int, tokens: dict, device: str, ip: Optional[str]):
    db.add(UserToken(
        user_id=user_id, access_token=hash_token(tokens["access_token"]),
        refresh_token=hash_token(tokens["refresh_token"]), device_info=device,
        ip_address=ip, access_expires=tokens["access_expires"],
        refresh_expires=tokens["refresh_expires"],
    ))


def authenticate_access_token(db: Session, token: str) -> Optional[User]:
    """同时校验 JWT 和服务端令牌状态，使退出登录立即生效。"""
    user_id = get_user_id_from_token(token)
    if not user_id:
        return None

    active_token = db.query(UserToken.id).filter(
        UserToken.user_id == user_id,
        UserToken.access_token == hash_token(token),
        UserToken.revoked == False,
        UserToken.access_expires > datetime.now(timezone.utc),
    ).first()
    if not active_token:
        return None

    return db.query(User).filter(
        User.id == user_id,
        User.status == "active",
    ).first()


def refresh_tokens(db: Session, refresh_token: str, ip: Optional[str]) -> dict:
    """轮换刷新令牌，并以条件更新避免同一令牌被重复使用。"""
    user_id = get_refresh_user_id(refresh_token)
    if not user_id:
        return {"success": False, "message": "刷新令牌无效或已过期"}

    now = datetime.now(timezone.utc)
    stored = db.query(UserToken).filter(
        UserToken.user_id == user_id,
        UserToken.refresh_token == hash_token(refresh_token),
        UserToken.revoked == False,
        UserToken.refresh_expires > now,
    ).first()
    user = db.query(User).filter(
        User.id == user_id,
        User.status == "active",
    ).first()
    if not stored or not user:
        return {"success": False, "message": "刷新令牌无效或已过期"}

    updated = db.query(UserToken).filter(
        UserToken.id == stored.id,
        UserToken.revoked == False,
        UserToken.refresh_expires > now,
    ).update({"revoked": True}, synchronize_session=False)
    if updated != 1:
        db.rollback()
        return {"success": False, "message": "刷新令牌无效或已过期"}

    tokens = create_token_pair(user.id)
    _save_token(db, user.id, tokens, "refresh", ip)
    db.commit()
    return {"success": True, "message": "令牌已刷新", "user": user, "tokens": tokens}


def revoke_all_tokens(db: Session, user_id: int):
    db.query(UserToken).filter(
        UserToken.user_id == user_id,
        UserToken.revoked == False,
    ).update({"revoked": True})
    db.commit()


def revoke_token(db: Session, user_id: int, access_token: str) -> bool:
    updated = db.query(UserToken).filter(
        UserToken.user_id == user_id,
        UserToken.access_token == hash_token(access_token),
        UserToken.revoked == False,
    ).update({"revoked": True}, synchronize_session=False)
    db.commit()
    return updated == 1


def change_password(db: Session, user: User, current_password: str,
                    new_password: str) -> dict:
    if not user.password_hash or not verify_password(current_password, user.password_hash):
        return {"success": False, "message": "当前密码错误"}
    user.password_hash = hash_password(new_password)
    db.query(UserToken).filter(
        UserToken.user_id == user.id,
        UserToken.revoked == False,
    ).update({"revoked": True}, synchronize_session=False)
    db.commit()
    return {"success": True, "message": "密码已更新，请重新登录"}

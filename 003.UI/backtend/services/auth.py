"""
LiveTrans — 认证服务 (PRD §4.7.2 ~ §4.7.8)
"""
import random
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models.user import User, VerificationCode, UserToken, UserDevice
from utils.security import hash_password, verify_password, create_token_pair
from config import (
    VERIFICATION_CODE_LENGTH, VERIFICATION_CODE_EXPIRE_SECONDS,
    VERIFICATION_CODE_RESEND_SECONDS, VERIFICATION_CODE_DAILY_LIMIT,
)


# ─── 验证码 ─────────────────────────────────────────────

def generate_code() -> str:
    """生成 6 位数字验证码"""
    return "".join([str(random.randint(0, 9)) for _ in range(VERIFICATION_CODE_LENGTH)])


def send_verification_code(db: Session, target: str, target_type: str,
                           scene: str, ip: Optional[str]) -> dict:
    """
    发送验证码 — PRD §4.7.2
    限制: 60秒内仅1次, 每天上限10次 (PRD §7.4)
    """
    now = datetime.now(timezone.utc)

    # 60秒内是否已发
    recent = db.query(VerificationCode).filter(
        VerificationCode.target == target,
        VerificationCode.target_type == target_type,
        VerificationCode.created_at >= now - timedelta(seconds=VERIFICATION_CODE_RESEND_SECONDS),
    ).first()
    if recent:
        remaining = max(1, VERIFICATION_CODE_RESEND_SECONDS -
                       int((now - recent.created_at.replace(tzinfo=timezone.utc)).total_seconds()))
        return {"success": False, "message": f"请 {remaining} 秒后重试"}

    # 每日上限
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = db.query(VerificationCode).filter(
        VerificationCode.target == target,
        VerificationCode.target_type == target_type,
        VerificationCode.created_at >= today_start,
    ).count()
    if today_count >= VERIFICATION_CODE_DAILY_LIMIT:
        return {"success": False, "message": "今日验证码次数已用完"}

    # 创建验证码
    code = generate_code()
    expires_at = now + timedelta(seconds=VERIFICATION_CODE_EXPIRE_SECONDS)
    vc = VerificationCode(
        target=target,
        target_type=target_type,
        code=code,
        scene=scene,
        ip_address=ip,
        expires_at=expires_at,
    )
    db.add(vc)
    db.commit()

    # 开发模式下打印验证码（生产环境改为发短信）
    print(f"\n{'='*50}")
    print(f"  [LiveTrans] 验证码: {code}")
    print(f"  发送至: {target} ({target_type})")
    print(f"  场景: {scene} | 过期时间: {expires_at}")
    print(f"{'='*50}\n")

    return {"success": True, "message": "验证码已发送", "expires_in": VERIFICATION_CODE_EXPIRE_SECONDS}


def verify_code(db: Session, target: str, target_type: str, code: str, scene: str) -> bool:
    """验证验证码是否有效"""
    vc = db.query(VerificationCode).filter(
        VerificationCode.target == target,
        VerificationCode.target_type == target_type,
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

def register_by_phone(db: Session, phone: str, code: str,
                      nickname: Optional[str], ip: Optional[str]) -> dict:
    """手机号 + 验证码 注册 — PRD §4.7.2"""
    # 验证码校验
    if not verify_code(db, phone, "phone", code, "register"):
        return {"success": False, "message": "验证码错误或已过期"}

    # 检查是否已注册
    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        return {"success": False, "message": "该手机号已注册，请直接登录"}

    # 创建用户
    user = User(
        nickname=nickname or f"用户_{phone[-4:]}",
        phone=phone,
        phone_verified=True,
        last_login_at=datetime.now(timezone.utc),
        last_login_ip=ip,
    )
    db.add(user)
    db.flush()

    # 生成 Token
    tokens = create_token_pair(user.id)
    save_token(db, user.id, tokens, "phone_register", ip)

    db.commit()
    return {"success": True, "message": "注册成功", "user": user, "tokens": tokens}


def register_by_email(db: Session, email: str, password: str,
                      nickname: Optional[str], ip: Optional[str]) -> dict:
    """邮箱 + 密码 注册"""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return {"success": False, "message": "该邮箱已注册"}

    user = User(
        nickname=nickname or email.split("@")[0],
        email=email,
        email_verified=False,
        password_hash=hash_password(password),    # bcrypt 12轮 (PRD §7.4)
        last_login_at=datetime.now(timezone.utc),
        last_login_ip=ip,
    )
    db.add(user)
    db.flush()

    tokens = create_token_pair(user.id)
    save_token(db, user.id, tokens, "email_register", ip)

    db.commit()
    return {"success": True, "message": "注册成功", "user": user, "tokens": tokens}


# ─── 登录 ───────────────────────────────────────────────

def login_by_phone(db: Session, phone: str, code: str, ip: Optional[str]) -> dict:
    """手机号 + 验证码 登录"""
    if not verify_code(db, phone, "phone", code, "login"):
        return {"success": False, "message": "验证码错误或已过期"}

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        return {"success": False, "message": "该手机号未注册，请先注册"}

    if user.status != "active":
        return {"success": False, "message": f"账户状态异常: {user.status}"}

    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = ip
    tokens = create_token_pair(user.id)
    save_token(db, user.id, tokens, "phone_login", ip)
    db.commit()

    return {"success": True, "message": "登录成功", "user": user, "tokens": tokens}


def login_by_email(db: Session, email: str, password: str, ip: Optional[str]) -> dict:
    """邮箱 + 密码 登录"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"success": False, "message": "邮箱未注册"}
    if not user.password_hash:
        return {"success": False, "message": "该账号使用手机号注册，请用验证码登录"}
    if not verify_password(password, user.password_hash):
        return {"success": False, "message": "密码错误"}

    if user.status != "active":
        return {"success": False, "message": f"账户状态异常: {user.status}"}

    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = ip
    tokens = create_token_pair(user.id)
    save_token(db, user.id, tokens, "email_login", ip)
    db.commit()

    return {"success": True, "message": "登录成功", "user": user, "tokens": tokens}


# ─── 令牌持久化 ──────────────────────────────────────────

def save_token(db: Session, user_id: int, tokens: dict, device_info: str, ip: Optional[str]):
    """保存 Token 到数据库 — PRD §4.7.3"""
    t = UserToken(
        user_id=user_id,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        device_info=device_info,
        ip_address=ip,
        access_expires=tokens["access_expires"],
        refresh_expires=tokens["refresh_expires"],
    )
    db.add(t)


def revoke_all_tokens(db: Session, user_id: int):
    """撤销用户所有 Token（退出登录/修改密码时调用）"""
    db.query(UserToken).filter(
        UserToken.user_id == user_id,
        UserToken.revoked == False,
    ).update({"revoked": True})
    db.commit()

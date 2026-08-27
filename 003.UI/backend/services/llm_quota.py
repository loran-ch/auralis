"""LLM Token 额度：滚动窗口用量统计、拦截与记账。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from config import (BRIEFING_LLM_MODEL, LLM_QUOTA_FREE_TOKENS,
                    LLM_QUOTA_PREMIUM_TOKENS, LLM_QUOTA_WINDOW_DAYS)
from models.llm_quota import LlmUsageEvent, UserLlmQuota
from models.user import User


class QuotaExceededError(RuntimeError):
    """用户近窗口内 LLM token 已达上限。"""

    def __init__(self, message: str = "LLM Token 额度已用尽，请联系管理员提升上限"):
        super().__init__(message)


def window_start(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now - timedelta(days=LLM_QUOTA_WINDOW_DAYS)


def default_token_limit(member_level: Optional[str]) -> int:
    if member_level == "premium":
        return int(LLM_QUOTA_PREMIUM_TOKENS)
    return int(LLM_QUOTA_FREE_TOKENS)


def get_token_limit(db: Session, user: User) -> int:
    row = db.query(UserLlmQuota).filter(UserLlmQuota.user_id == user.id).first()
    if row and row.token_limit is not None:
        return max(0, int(row.token_limit))
    return default_token_limit(getattr(user, "member_level", None))


def used_tokens(db: Session, user_id: int, *, since: Optional[datetime] = None) -> int:
    since = since or window_start()
    # MySQL DATETIME 常无时区；比较时去掉 tzinfo 避免 driver 告警。
    since_naive = since.replace(tzinfo=None) if since.tzinfo else since
    total = (
        db.query(func.coalesce(func.sum(LlmUsageEvent.total_tokens), 0))
        .filter(LlmUsageEvent.user_id == user_id, LlmUsageEvent.created_at >= since_naive)
        .scalar()
    )
    return int(total or 0)


def get_quota_snapshot(db: Session, user: User) -> dict:
    limit = get_token_limit(db, user)
    used = used_tokens(db, user.id)
    override = db.query(UserLlmQuota).filter(UserLlmQuota.user_id == user.id).first()
    return {
        "user_id": int(user.id),
        "token_limit": limit,
        "tokens_used": used,
        "tokens_remaining": max(0, limit - used),
        "window_days": LLM_QUOTA_WINDOW_DAYS,
        "member_level": getattr(user, "member_level", None) or "free",
        "has_custom_limit": bool(override and override.token_limit is not None),
        "custom_token_limit": override.token_limit if override else None,
    }


def assert_within_quota(db: Session, user_id: int) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise QuotaExceededError("用户不存在")
    snap = get_quota_snapshot(db, user)
    if snap["tokens_used"] >= snap["token_limit"]:
        raise QuotaExceededError(
            f"近 {LLM_QUOTA_WINDOW_DAYS} 天 LLM Token 已用尽"
            f"（{snap['tokens_used']}/{snap['token_limit']}），请联系管理员提升上限"
        )
    return snap


def estimate_tokens_from_text(*parts: str) -> int:
    chars = sum(len(part or "") for part in parts)
    return max(1, (chars + 3) // 4)


def parse_usage_from_response(data: dict, *, prompt_hint: str = "",
                              completion_hint: str = "") -> dict:
    usage = data.get("usage") if isinstance(data, dict) else None
    if isinstance(usage, dict):
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or (prompt + completion))
        if total > 0:
            return {
                "prompt_tokens": max(0, prompt),
                "completion_tokens": max(0, completion),
                "total_tokens": max(0, total),
            }
    estimated = estimate_tokens_from_text(prompt_hint, completion_hint)
    return {
        "prompt_tokens": estimated,
        "completion_tokens": 0,
        "total_tokens": estimated,
    }


def record_usage(
    db: Session,
    *,
    user_id: int,
    source: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    model: Optional[str] = None,
    commit: bool = True,
) -> LlmUsageEvent:
    total = int(total_tokens or (prompt_tokens + completion_tokens))
    if total <= 0:
        total = 1
    event = LlmUsageEvent(
        user_id=user_id,
        source=(source or "assistant")[:32],
        prompt_tokens=max(0, int(prompt_tokens)),
        completion_tokens=max(0, int(completion_tokens)),
        total_tokens=max(0, total),
        model=(model or BRIEFING_LLM_MODEL)[:64],
        created_at=datetime.utcnow(),
    )
    db.add(event)
    if commit:
        db.commit()
    else:
        db.flush()
    return event


def set_user_token_limit(
    db: Session,
    *,
    user: User,
    token_limit: Optional[int],
    admin: User,
    ip_address: Optional[str] = None,
) -> dict:
    from services.admin import write_audit_log

    if token_limit is not None and token_limit < 0:
        raise ValueError("token_limit 不能为负数")

    row = db.query(UserLlmQuota).filter(UserLlmQuota.user_id == user.id).first()
    old_limit = row.token_limit if row else None
    if row is None:
        row = UserLlmQuota(user_id=user.id)
        db.add(row)
    row.token_limit = token_limit
    row.updated_by = admin.id
    row.updated_at = datetime.utcnow()
    write_audit_log(
        db,
        admin,
        action="user.quota_update",
        target_type="user",
        target_id=user.id,
        detail={"old_token_limit": old_limit, "new_token_limit": token_limit},
        ip_address=ip_address,
    )
    db.commit()
    return get_quota_snapshot(db, user)

"""LiveTrans Voice — 管理后台业务逻辑"""
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from config import DB_POOL_SIZE, ENVIRONMENT, LLM_QUOTA_WINDOW_DAYS
from models.admin import AuditLog
from models.lecture import Bookmark, Lecture, Transcription
from models.llm_quota import LlmUsageEvent
from models.user import User
from services.llm_quota import get_quota_snapshot, window_start


# ─── 审计日志工具 ─────────────────────────────────────────

def write_audit_log(
    db: Session,
    admin: User,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    detail: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    entry = AuditLog(
        admin_id=admin.id,
        admin_name=admin.nickname,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(entry)
    db.flush()
    return entry


def _day_start_utc(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _count_active_users(db: Session, since: datetime, until: Optional[datetime] = None) -> int:
    """有登录或课堂/用量行为的去重用户数。"""
    since_naive = since.replace(tzinfo=None) if since.tzinfo else since
    until_naive = until.replace(tzinfo=None) if until and until.tzinfo else until

    login_q = db.query(User.id.label("uid")).filter(User.last_login_at >= since_naive)
    if until_naive:
        login_q = login_q.filter(User.last_login_at < until_naive)

    lecture_q = db.query(Lecture.user_id.label("uid")).filter(Lecture.created_at >= since_naive)
    if until_naive:
        lecture_q = lecture_q.filter(Lecture.created_at < until_naive)

    usage_q = db.query(LlmUsageEvent.user_id.label("uid")).filter(
        LlmUsageEvent.created_at >= since_naive
    )
    if until_naive:
        usage_q = usage_q.filter(LlmUsageEvent.created_at < until_naive)

    union_sub = login_q.union(lecture_q, usage_q).subquery()
    return int(db.query(func.count()).select_from(union_sub).scalar() or 0)


# ─── Dashboard ────────────────────────────────────────────

def get_dashboard_stats(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    today = _day_start_utc(now)
    week_ago = today - timedelta(days=7)
    since_30d = window_start(now)

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_today = _count_active_users(db, today)
    active_30d = _count_active_users(db, since_30d)
    new_this_week = (
        db.query(func.count(User.id))
        .filter(User.created_at >= week_ago.replace(tzinfo=None))
        .scalar()
        or 0
    )
    total_lectures = db.query(func.count(Lecture.id)).scalar() or 0
    total_transcriptions = db.query(func.count(Transcription.id)).scalar() or 0
    total_bookmarks = db.query(func.count(Bookmark.id)).scalar() or 0
    admin_count = (
        db.query(func.count(User.id))
        .filter(User.role.in_(("admin", "super_admin")))
        .scalar()
        or 0
    )
    llm_tokens_30d = int(
        db.query(func.coalesce(func.sum(LlmUsageEvent.total_tokens), 0))
        .filter(LlmUsageEvent.created_at >= since_30d.replace(tzinfo=None))
        .scalar()
        or 0
    )

    system_info = {
        "environment": ENVIRONMENT,
        "version": "1.4.0",
        "db_pool_size": DB_POOL_SIZE,
        "llm_quota_window_days": LLM_QUOTA_WINDOW_DAYS,
    }

    return {
        "total_users": total_users,
        "active_today": active_today,
        "active_30d": active_30d,
        "new_this_week": new_this_week,
        "total_lectures": total_lectures,
        "total_transcriptions": total_transcriptions,
        "total_bookmarks": total_bookmarks,
        "admin_count": admin_count,
        "llm_tokens_30d": llm_tokens_30d,
        "system_info": system_info,
    }


def get_timeseries(db: Session, *, days: int = 30) -> dict:
    days = max(1, min(90, int(days)))
    today = _day_start_utc()
    start = today - timedelta(days=days - 1)
    points = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        next_day = day + timedelta(days=1)
        day_naive = day.replace(tzinfo=None)
        next_naive = next_day.replace(tzinfo=None)
        dau = _count_active_users(db, day, next_day)
        new_users = int(
            db.query(func.count(User.id))
            .filter(User.created_at >= day_naive, User.created_at < next_naive)
            .scalar()
            or 0
        )
        completed = int(
            db.query(func.count(Lecture.id))
            .filter(
                Lecture.status == "completed",
                Lecture.created_at >= day_naive,
                Lecture.created_at < next_naive,
            )
            .scalar()
            or 0
        )
        tokens = int(
            db.query(func.coalesce(func.sum(LlmUsageEvent.total_tokens), 0))
            .filter(
                LlmUsageEvent.created_at >= day_naive,
                LlmUsageEvent.created_at < next_naive,
            )
            .scalar()
            or 0
        )
        points.append({
            "date": day.date().isoformat(),
            "dau": dau,
            "new_users": new_users,
            "completed_lectures": completed,
            "llm_tokens": tokens,
        })
    return {"days": days, "points": points}


# ─── 用户管理 ─────────────────────────────────────────────

def list_users(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status: Optional[str] = None,
    role: Optional[str] = None,
) -> dict:
    query = db.query(User)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                User.nickname.ilike(like),
                User.phone.ilike(like),
                User.email.ilike(like),
                User.username.ilike(like),
            )
        )
    if status:
        query = query.filter(User.status == status)
    if role:
        query = query.filter(User.role == role)

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size
    items = (
        query.order_by(User.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    enriched = []
    for user in items:
        snap = get_quota_snapshot(db, user)
        enriched.append({
            "user": user,
            "tokens_used": snap["tokens_used"],
            "token_limit": snap["token_limit"],
            "has_custom_limit": snap["has_custom_limit"],
        })

    return {
        "items": enriched,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_user_detail(db: Session, user_id: int) -> Optional[dict]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    snap = get_quota_snapshot(db, user)
    return {"user": user, **snap}


def update_user_status(
    db: Session,
    user_id: int,
    new_status: str,
    admin: User,
    ip_address: Optional[str] = None,
) -> dict:
    if user_id == admin.id:
        return {"success": False, "message": "不能修改自己的状态"}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "用户不存在"}
    if user.role == "super_admin" and admin.role != "super_admin":
        return {"success": False, "message": "不能修改超级管理员的状态"}

    old_status = user.status
    user.status = new_status
    write_audit_log(
        db,
        admin,
        action=f"user.status_{new_status}",
        target_type="user",
        target_id=user_id,
        detail={"old_status": old_status, "new_status": new_status},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)

    status_text = {"active": "已启用", "disabled": "已禁用"}
    return {"success": True, "message": f"用户{status_text.get(new_status, new_status)}"}


def update_user_role(
    db: Session,
    user_id: int,
    new_role: str,
    admin: User,
    ip_address: Optional[str] = None,
) -> dict:
    if user_id == admin.id:
        return {"success": False, "message": "不能修改自己的角色"}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "用户不存在"}

    if user.role == "super_admin" and new_role != "super_admin":
        super_count = (
            db.query(func.count(User.id))
            .filter(User.role == "super_admin")
            .scalar()
            or 0
        )
        if super_count <= 1:
            return {"success": False, "message": "不能撤销最后一个超级管理员"}

    old_role = user.role
    user.role = new_role
    write_audit_log(
        db,
        admin,
        action=f"user.role_{new_role}",
        target_type="user",
        target_id=user_id,
        detail={"old_role": old_role, "new_role": new_role},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)

    role_text = {"user": "普通用户", "admin": "教师(admin)", "super_admin": "超级管理员"}
    return {"success": True, "message": f"角色已更新为{role_text.get(new_role, new_role)}"}


def delete_user(
    db: Session,
    user_id: int,
    admin: User,
    ip_address: Optional[str] = None,
) -> dict:
    if user_id == admin.id:
        return {"success": False, "message": "不能删除自己"}

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"success": False, "message": "用户不存在"}
    if user.role == "super_admin":
        return {"success": False, "message": "不能删除超级管理员"}

    user.status = "deleted"
    user.deleted_at = datetime.now(timezone.utc)
    write_audit_log(
        db,
        admin,
        action="user.delete",
        target_type="user",
        target_id=user_id,
        detail={"nickname": user.nickname, "phone": user.phone},
        ip_address=ip_address,
    )
    db.commit()
    return {"success": True, "message": "用户已删除"}


# ─── 课堂管理 ─────────────────────────────────────────────

def list_lectures(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict:
    query = db.query(Lecture, User.nickname, User.email).join(
        User, Lecture.user_id == User.id, isouter=True
    )

    if search:
        like = f"%{search}%"
        query = query.filter(
            Lecture.course_name.ilike(like) | User.nickname.ilike(like)
        )
    if status:
        query = query.filter(Lecture.status == status)
    if user_id is not None:
        query = query.filter(Lecture.user_id == user_id)

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size
    rows = (
        query.order_by(Lecture.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = []
    for lecture, nickname, email in rows:
        items.append(
            {
                "id": lecture.id,
                "user_id": lecture.user_id,
                "user_nickname": nickname,
                "course_name": lecture.course_name,
                "source_lang": lecture.source_lang,
                "target_lang": lecture.target_lang,
                "duration_seconds": lecture.duration_seconds or 0,
                "sentence_count": lecture.sentence_count or 0,
                "status": lecture.status,
                "lecture_date": lecture.lecture_date,
                "created_at": lecture.created_at,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def delete_lecture(
    db: Session,
    lecture_id: int,
    admin: User,
    ip_address: Optional[str] = None,
) -> dict:
    lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()
    if not lecture:
        return {"success": False, "message": "课堂不存在"}

    snapshot = {
        "course_name": lecture.course_name,
        "user_id": lecture.user_id,
        "status": lecture.status,
    }

    db.delete(lecture)
    write_audit_log(
        db,
        admin,
        action="lecture.delete",
        target_type="lecture",
        target_id=lecture_id,
        detail=snapshot,
        ip_address=ip_address,
    )
    db.commit()
    return {"success": True, "message": "课堂已删除"}


# ─── 审计日志查询 ─────────────────────────────────────────

def get_audit_logs(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    admin_id: Optional[int] = None,
    action: Optional[str] = None,
) -> dict:
    query = db.query(AuditLog)

    if admin_id is not None:
        query = query.filter(AuditLog.admin_id == admin_id)
    if action:
        query = query.filter(AuditLog.action == action)

    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size
    items = (
        query.order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }

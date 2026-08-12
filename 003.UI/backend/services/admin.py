"""LiveTrans Voice — 管理后台业务逻辑"""
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from config import ENVIRONMENT, DB_POOL_SIZE
from models.admin import AuditLog
from models.lecture import Bookmark, Lecture, Transcription
from models.user import User


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


# ─── Dashboard ────────────────────────────────────────────

def get_dashboard_stats(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_today = (
        db.query(func.count(User.id))
        .filter(User.last_login_at >= today)
        .scalar()
        or 0
    )
    new_this_week = (
        db.query(func.count(User.id))
        .filter(User.created_at >= week_ago)
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

    system_info = {
        "environment": ENVIRONMENT,
        "version": "1.3.0",
        "db_pool_size": DB_POOL_SIZE,
    }

    return {
        "total_users": total_users,
        "active_today": active_today,
        "new_this_week": new_this_week,
        "total_lectures": total_lectures,
        "total_transcriptions": total_transcriptions,
        "total_bookmarks": total_bookmarks,
        "admin_count": admin_count,
        "system_info": system_info,
    }


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
            User.nickname.ilike(like) | User.phone.ilike(like) | User.email.ilike(like)
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

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


def get_user_detail(db: Session, user_id: int) -> Optional[dict]:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    lecture_count = (
        db.query(func.count(Lecture.id))
        .filter(Lecture.user_id == user_id)
        .scalar()
        or 0
    )
    return {"user": user, "lecture_count": lecture_count}


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

    # 防止撤销最后一个超管
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

    role_text = {"user": "普通用户", "admin": "管理员", "super_admin": "超级管理员"}
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

    # 软删除：设置状态为 deleted
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

    # 记录快照用于审计
    snapshot = {
        "course_name": lecture.course_name,
        "user_id": lecture.user_id,
        "status": lecture.status,
    }

    # CASCADE 自动清理 bookmark + transcription
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

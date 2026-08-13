"""系统注册开关。

注册状态保存在管理员审计日志中，因此现有生产数据库无需额外迁移，
每次暂停或恢复也都有完整的操作记录。
"""
from typing import Optional

from sqlalchemy.orm import Session

from models.admin import AuditLog
from models.user import User


REGISTRATION_SETTING_ACTION = "system.registration.update"


def get_registration_setting(db: Session) -> dict:
    latest = (
        db.query(AuditLog)
        .filter(AuditLog.action == REGISTRATION_SETTING_ACTION)
        .order_by(AuditLog.id.desc())
        .first()
    )
    enabled = True
    if latest and isinstance(latest.detail, dict):
        enabled = latest.detail.get("enabled") is not False
    return {
        "enabled": enabled,
        "message": "当前允许新用户注册" if enabled else "管理员已暂停新用户注册",
        "updated_at": latest.created_at if latest else None,
        "updated_by": latest.admin_name if latest else None,
    }


def registration_is_enabled(db: Session) -> bool:
    return get_registration_setting(db)["enabled"]


def update_registration_setting(
    db: Session,
    enabled: bool,
    admin: User,
    ip_address: Optional[str] = None,
) -> dict:
    current = get_registration_setting(db)
    if current["enabled"] == enabled:
        return current

    entry = AuditLog(
        admin_id=admin.id,
        admin_name=admin.nickname or admin.username,
        action=REGISTRATION_SETTING_ACTION,
        target_type="system",
        detail={
            "enabled": enabled,
            "previous_enabled": current["enabled"],
        },
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {
        "enabled": enabled,
        "message": "已恢复新用户注册" if enabled else "已暂停新用户注册",
        "updated_at": entry.created_at,
        "updated_by": entry.admin_name,
    }

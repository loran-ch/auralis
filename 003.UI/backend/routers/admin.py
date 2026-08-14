"""LiveTrans Voice — 管理后台路由"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from database import get_db
from middleware.admin_auth import require_admin, require_super_admin
from models.user import User
from schemas.admin import (
    AdminLectureResp,
    AdminUserResp,
    AdminUserRoleReq,
    AdminUserStatusReq,
    AuditLogResp,
    DashboardStatsResp,
    PageResp,
    RegistrationSettingReq,
    RegistrationSettingResp,
)
from schemas.auth import MsgResp
from schemas.guide import GuideResp, GuideUpdateReq
from services import admin as admin_service
from services.guide import get_guide, update_guide
from services.registration import (get_registration_setting,
                                   update_registration_setting)

router = APIRouter(prefix="/api/admin", tags=["管理员"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ─── Dashboard ────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardStatsResp)
def api_dashboard(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """系统概览统计"""
    stats = admin_service.get_dashboard_stats(db)
    return DashboardStatsResp(**stats)


@router.get("/settings/registration", response_model=RegistrationSettingResp)
def api_registration_setting(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查看新用户注册状态。"""
    return RegistrationSettingResp(**get_registration_setting(db))


@router.patch("/settings/registration", response_model=RegistrationSettingResp)
def api_update_registration_setting(
    req: RegistrationSettingReq,
    request: Request,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """暂停或恢复新用户注册（仅超级管理员）。"""
    result = update_registration_setting(
        db, req.enabled, admin, _client_ip(request)
    )
    return RegistrationSettingResp(**result)


# ─── 用户管理 ─────────────────────────────────────────────

@router.get("/users", response_model=PageResp[AdminUserResp])
def api_list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=128),
    status: Optional[str] = Query(None, pattern=r"^(active|disabled|deleting|deleted)$"),
    role: Optional[str] = Query(None, pattern=r"^(user|admin|super_admin)$"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """用户列表（分页 + 搜索 + 筛选）"""
    result = admin_service.list_users(db, page, page_size, search, status, role)
    return PageResp(
        items=[AdminUserResp.model_validate(item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.get("/users/{user_id}", response_model=AdminUserResp)
def api_get_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """用户详情"""
    result = admin_service.get_user_detail(db, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="用户不存在")
    return AdminUserResp.model_validate(result["user"])


@router.patch("/users/{user_id}/status", response_model=MsgResp)
def api_update_user_status(
    user_id: int,
    req: AdminUserStatusReq,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新用户状态（启用/禁用）"""
    result = admin_service.update_user_status(
        db, user_id, req.status, admin, _client_ip(request)
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return MsgResp(message=result["message"])


@router.patch("/users/{user_id}/role", response_model=MsgResp)
def api_update_user_role(
    user_id: int,
    req: AdminUserRoleReq,
    request: Request,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """更新用户角色（仅超管）"""
    result = admin_service.update_user_role(
        db, user_id, req.role, admin, _client_ip(request)
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return MsgResp(message=result["message"])


@router.delete("/users/{user_id}", response_model=MsgResp)
def api_delete_user(
    user_id: int,
    request: Request,
    admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """删除用户（软删除，仅超管）"""
    result = admin_service.delete_user(db, user_id, admin, _client_ip(request))
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return MsgResp(message=result["message"])


# ─── 课堂管理 ─────────────────────────────────────────────

@router.get("/lectures", response_model=PageResp[AdminLectureResp])
def api_list_lectures(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=128),
    status: Optional[str] = Query(
        None, pattern=r"^(recording|paused|completed|failed)$"
    ),
    user_id: Optional[int] = Query(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """课堂列表（分页 + 搜索 + 筛选）"""
    result = admin_service.list_lectures(db, page, page_size, search, status, user_id)
    return PageResp(
        items=[AdminLectureResp(**item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.delete("/lectures/{lecture_id}", response_model=MsgResp)
def api_delete_lecture(
    lecture_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除课堂（CASCADE 清理关联数据）"""
    result = admin_service.delete_lecture(db, lecture_id, admin, _client_ip(request))
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return MsgResp(message=result["message"])


# ─── 功能说明 ─────────────────────────────────────────────

@router.get("/guides/{slug}", response_model=GuideResp)
def api_admin_get_guide(
    slug: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查看前台功能说明文案。"""
    return GuideResp(**get_guide(db, slug))


@router.put("/guides/{slug}", response_model=GuideResp)
def api_admin_update_guide(
    slug: str,
    req: GuideUpdateReq,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """编辑前台「说明」按钮展示的内容。"""
    try:
        result = update_guide(
            db,
            slug,
            req.model_dump(),
            admin,
            _client_ip(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GuideResp(**result)


# ─── 审计日志 ─────────────────────────────────────────────

@router.get("/audit-logs", response_model=PageResp[AuditLogResp])
def api_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None, max_length=64),
    super_admin: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """审计日志列表（仅超管）"""
    result = admin_service.get_audit_logs(db, page, page_size, admin_id, action)
    return PageResp(
        items=[AuditLogResp.model_validate(item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )

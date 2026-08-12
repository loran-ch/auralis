"""LiveTrans Voice — 管理后台请求/响应 Schema"""
from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ─── 通用分页 ─────────────────────────────────────────────

class PageResp(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── Dashboard ────────────────────────────────────────────

class DashboardStatsResp(BaseModel):
    total_users: int
    active_today: int
    new_this_week: int
    total_lectures: int
    total_transcriptions: int
    total_bookmarks: int
    admin_count: int
    system_info: dict


# ─── 用户管理 ─────────────────────────────────────────────

class AdminUserResp(BaseModel):
    id: int
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "user"
    status: str = "active"
    member_level: str = "free"
    university: Optional[str] = None
    major: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class AdminUserStatusReq(BaseModel):
    status: str = Field(..., pattern=r"^(active|disabled)$")


class AdminUserRoleReq(BaseModel):
    role: str = Field(..., pattern=r"^(user|admin|super_admin)$")


# ─── 课堂管理 ─────────────────────────────────────────────

class AdminLectureResp(BaseModel):
    id: int
    user_id: int
    user_nickname: Optional[str] = None
    course_name: str
    source_lang: str
    target_lang: str
    duration_seconds: int = 0
    sentence_count: int = 0
    status: str = "completed"
    lecture_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ─── 审计日志 ─────────────────────────────────────────────

class AuditLogResp(BaseModel):
    id: int
    admin_id: int
    admin_name: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    detail: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

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
    active_30d: int = 0
    new_this_week: int
    total_lectures: int
    total_transcriptions: int
    total_bookmarks: int
    admin_count: int
    llm_tokens_30d: int = 0
    system_info: dict


class TimeseriesPoint(BaseModel):
    date: str
    dau: int = 0
    new_users: int = 0
    completed_lectures: int = 0
    llm_tokens: int = 0


class TimeseriesResp(BaseModel):
    days: int
    points: list[TimeseriesPoint]


class RegistrationSettingReq(BaseModel):
    enabled: bool


class RegistrationSettingResp(BaseModel):
    enabled: bool
    message: str
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


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
    tokens_used: int = 0
    token_limit: int = 0
    has_custom_limit: bool = False
    model_config = {"from_attributes": True}


class AdminUserStatusReq(BaseModel):
    status: str = Field(..., pattern=r"^(active|disabled)$")


class AdminUserRoleReq(BaseModel):
    role: str = Field(..., pattern=r"^(user|admin|super_admin)$")


class AdminUserQuotaReq(BaseModel):
    token_limit: Optional[int] = Field(
        None,
        ge=0,
        description="自定义滚动窗口 LLM token 上限；null 表示恢复会员默认值",
    )


class AdminUserQuotaResp(BaseModel):
    user_id: int
    token_limit: int
    tokens_used: int
    tokens_remaining: int
    window_days: int
    member_level: str = "free"
    has_custom_limit: bool = False
    custom_token_limit: Optional[int] = None


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

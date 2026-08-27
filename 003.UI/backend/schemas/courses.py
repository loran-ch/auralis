"""课程中心 API Schema。"""
from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.lecture import LectureResp
from schemas.preferences import LANG_PATTERN, CourseScheduleResp


class CourseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    professor_name: Optional[str] = Field(None, max_length=128)
    room: Optional[str] = Field(None, max_length=64)
    term: Optional[str] = Field(None, max_length=64)
    source_lang: str = Field(default="en", pattern=LANG_PATTERN)
    target_lang: str = Field(default="zh-CN", pattern=LANG_PATTERN)
    translation_enabled: bool = False
    color: str = Field(default="#2563EB", pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("name", "professor_name", "room", "term")
    @classmethod
    def strip_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value and cls is not None:
            return None
        return value

    @field_validator("name")
    @classmethod
    def require_name(cls, value: Optional[str]) -> str:
        if not value:
            raise ValueError("课程名称不能为空")
        return value


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    professor_name: Optional[str] = Field(None, max_length=128)
    room: Optional[str] = Field(None, max_length=64)
    term: Optional[str] = Field(None, max_length=64)
    source_lang: Optional[str] = Field(None, pattern=LANG_PATTERN)
    target_lang: Optional[str] = Field(None, pattern=LANG_PATTERN)
    translation_enabled: Optional[bool] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None

    @field_validator("name", "professor_name", "room", "term")
    @classmethod
    def strip_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value is not None else None

    @field_validator("name")
    @classmethod
    def require_nonempty_name(cls, value: Optional[str]) -> Optional[str]:
        if value == "":
            raise ValueError("课程名称不能为空")
        return value

    model_config = ConfigDict(extra="forbid")


class CourseResp(BaseModel):
    id: int
    name: str
    professor_name: Optional[str] = None
    room: Optional[str] = None
    term: Optional[str] = None
    source_lang: str
    target_lang: str
    translation_enabled: bool = True
    color: str = "#2563EB"
    is_active: bool = True
    is_public: bool = False
    owner_id: Optional[int] = None
    owner_nickname: Optional[str] = None
    is_owner: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class CourseScheduleAttachReq(BaseModel):
    day_of_week: int = Field(..., ge=1, le=7)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("结束时间必须晚于开始时间")
        return self


class CourseOverviewResp(BaseModel):
    course: CourseResp
    lecture_count: int = 0
    completed_lecture_count: int = 0
    total_duration_seconds: int = 0
    schedules: list[CourseScheduleResp] = Field(default_factory=list)
    recent_lectures: list[LectureResp] = Field(default_factory=list)
    can_manage: bool = True

"""用户设置、语言、统计和课程表的 API Schema。"""
from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, Field, model_validator


LANG_PATTERN = r"^[a-z]{2}(?:-[A-Z]{2})?$"


class LanguageResp(BaseModel):
    code: str
    name_native: str
    name_en: str
    flag_emoji: Optional[str] = None
    region: Optional[str] = None
    supports_offline: bool = False
    offline_size_mb: Optional[int] = None
    model_config = {"from_attributes": True}


class UserSettingsResp(BaseModel):
    default_source_lang: str = "auto"
    default_target_lang: str = "zh-CN"
    default_engine: str = "default"
    translation_mode: str = "auto"
    font_size: str = "medium"
    dark_mode: str = "system"
    flash_mode: str = "auto"
    ocr_frequency: str = "medium"
    history_auto_clean: bool = True
    history_keep_count: int = 500
    cloud_sync_enabled: bool = False
    sync_history: bool = True
    sync_bookmarks: bool = True
    sync_settings: bool = True
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class UserSettingsUpdate(BaseModel):
    default_source_lang: Optional[str] = Field(None, pattern=r"^(auto|[a-z]{2}(?:-[A-Z]{2})?)$")
    default_target_lang: Optional[str] = Field(None, pattern=LANG_PATTERN)
    default_engine: Optional[str] = Field(None, min_length=1, max_length=32)
    translation_mode: Optional[str] = Field(None, pattern=r"^(online|offline|auto)$")
    font_size: Optional[str] = Field(None, pattern=r"^(small|medium|large)$")
    dark_mode: Optional[str] = Field(None, pattern=r"^(system|light|dark)$")
    flash_mode: Optional[str] = Field(None, pattern=r"^(auto|on|off)$")
    ocr_frequency: Optional[str] = Field(None, pattern=r"^(high|medium|low)$")
    history_auto_clean: Optional[bool] = None
    history_keep_count: Optional[int] = Field(None, ge=50, le=10000)
    cloud_sync_enabled: Optional[bool] = None
    sync_history: Optional[bool] = None
    sync_bookmarks: Optional[bool] = None
    sync_settings: Optional[bool] = None
    model_config = {"extra": "forbid"}


class UserStatsResp(BaseModel):
    total_seconds: int
    total_hours: float
    lecture_count: int
    bookmark_count: int
    weekly_record_seconds: int
    weekly_record_hours: float
    weekly_bookmark_count: int
    current_streak_days: int
    exam_mastery_improve: int = 0


class CourseScheduleCreate(BaseModel):
    course_name: str = Field(..., min_length=1, max_length=256)
    source_lang: str = Field(default="en", pattern=LANG_PATTERN)
    target_lang: str = Field(default="zh-CN", pattern=LANG_PATTERN)
    day_of_week: int = Field(..., ge=1, le=7)
    start_time: time
    end_time: time
    room: Optional[str] = Field(None, max_length=64)
    professor_name: Optional[str] = Field(None, max_length=128)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time >= self.end_time:
            raise ValueError("结束时间必须晚于开始时间")
        self.course_name = self.course_name.strip()
        if not self.course_name:
            raise ValueError("课程名称不能为空")
        self.room = self.room.strip() or None if self.room is not None else None
        self.professor_name = (
            self.professor_name.strip() or None
            if self.professor_name is not None else None
        )
        return self


class CourseScheduleUpdate(BaseModel):
    course_name: Optional[str] = Field(None, min_length=1, max_length=256)
    source_lang: Optional[str] = Field(None, pattern=LANG_PATTERN)
    target_lang: Optional[str] = Field(None, pattern=LANG_PATTERN)
    day_of_week: Optional[int] = Field(None, ge=1, le=7)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    room: Optional[str] = Field(None, max_length=64)
    professor_name: Optional[str] = Field(None, max_length=128)
    is_active: Optional[bool] = None
    model_config = {"extra": "forbid"}


class CourseScheduleResp(BaseModel):
    id: int
    course_name: str
    source_lang: str
    target_lang: str
    day_of_week: int
    start_time: time
    end_time: time
    room: Optional[str] = None
    professor_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

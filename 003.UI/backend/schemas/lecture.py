"""LiveTrans Voice — 课堂/转录/收藏 Schema"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class StartLectureReq(BaseModel):
    course_name: str = Field(default="未命名课程", min_length=1, max_length=256)
    source_lang: str = Field(default="de", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    target_lang: str = Field(default="zh-CN", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")

    @field_validator("course_name")
    @classmethod
    def normalize_course_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("课程名称不能为空")
        return value


class LectureResp(BaseModel):
    id: int
    course_name: str
    source_lang: str
    target_lang: str
    status: str
    duration_seconds: int = 0
    sentence_count: int = 0
    bookmark_count: int = 0
    audio_url: Optional[str] = None
    audio_size_bytes: Optional[int] = None
    location_name: Optional[str] = None
    room: Optional[str] = None
    subject_tags: Optional[list[str]] = None
    exported: bool = False
    lecture_date: Optional[date] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TranscriptionResp(BaseModel):
    id: int
    sentence_order: int
    source_text: str
    source_lang: str
    translated_text: str
    target_lang: str
    is_bookmarked: bool = False
    bookmark_tag: Optional[str] = None
    ocr_confidence: Optional[float] = None
    engine: str = "default"
    mode: str = "online"
    start_offset_ms: int = 0
    end_offset_ms: Optional[int] = None
    recorded_at: Optional[datetime] = None
    translation_success: Optional[bool] = None
    translation_provider: Optional[str] = None
    translation_warning: Optional[str] = None
    context_applied: Optional[bool] = None
    model_config = {"from_attributes": True}


class BookmarkReq(BaseModel):
    transcription_id: int = Field(..., gt=0)
    tag: str = Field(default="important", pattern="^(important|question|exam|definition)$")
    note: Optional[str] = Field(None, max_length=2000)


class BookmarkResp(BaseModel):
    bookmark_id: int
    tag: str
    source_text: str
    translated_text: str
    note: Optional[str] = None


class LectureUpdateReq(BaseModel):
    course_name: Optional[str] = Field(None, min_length=1, max_length=256)
    location_name: Optional[str] = Field(None, max_length=256)
    room: Optional[str] = Field(None, max_length=64)
    subject_tags: Optional[list[str]] = Field(None, max_length=20)
    exported: Optional[bool] = None

    @field_validator("course_name", "location_name", "room")
    @classmethod
    def strip_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("subject_tags")
    @classmethod
    def normalize_tags(cls, values: Optional[list[str]]) -> Optional[list[str]]:
        if values is None:
            return None
        normalized = []
        for value in values:
            value = value.strip()
            if value and value not in normalized:
                if len(value) > 32:
                    raise ValueError("单个标签不能超过 32 个字符")
                normalized.append(value)
        return normalized


class BookmarkListItem(BaseModel):
    bookmark_id: int
    transcription_id: int
    lecture_id: int
    tag: str
    note: Optional[str] = None
    source_text: str
    translated_text: str
    course_name: str
    created_at: Optional[datetime] = None


class BookmarkUpdateReq(BaseModel):
    tag: Optional[str] = Field(None, pattern="^(important|question|exam|definition)$")
    note: Optional[str] = Field(None, max_length=2000)


class GenerateBriefingReq(BaseModel):
    force: bool = False


class BriefingCitation(BaseModel):
    text: str
    source_text: str = ""
    sentence_order: int
    start_offset_ms: int = 0
    tag: Optional[str] = None


class BriefingOutlineItem(BaseModel):
    title: str
    summary: str = ""
    start_order: int
    end_order: int
    start_offset_ms: int = 0


class BriefingTerm(BaseModel):
    term: str
    explanation: str = ""
    source_text: str = ""
    sentence_order: int
    start_offset_ms: int = 0


class BriefingResp(BaseModel):
    lecture_id: int
    status: str
    provider: Optional[str] = None
    overview: str = ""
    outline: list[BriefingOutlineItem] = Field(default_factory=list)
    key_points: list[BriefingCitation] = Field(default_factory=list)
    exam_hints: list[BriefingCitation] = Field(default_factory=list)
    questions: list[BriefingCitation] = Field(default_factory=list)
    terms: list[BriefingTerm] = Field(default_factory=list)
    source_sentence_count: int = 0
    error_message: Optional[str] = None
    generated_at: Optional[datetime] = None


class AssistantHistoryItem(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=2000)


class AssistantAskReq(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    history: list[AssistantHistoryItem] = Field(default_factory=list, max_length=6)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("问题不能为空")
        return value


class AssistantCitation(BaseModel):
    sentence_order: int
    start_offset_ms: int = 0
    source_text: str = ""
    translated_text: str = ""
    tag: Optional[str] = None


class AssistantAskResp(BaseModel):
    answer: str
    citations: list[AssistantCitation] = Field(default_factory=list)
    provider: str = "extractive"
    used_briefing: bool = False

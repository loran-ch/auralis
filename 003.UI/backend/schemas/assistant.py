"""独立学习助手的会话与问答 Schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class AssistantThreadCreate(BaseModel):
    course_id: Optional[int] = Field(None, gt=0)
    lecture_ids: list[int] = Field(default_factory=list, max_length=50)
    title: Optional[str] = Field(None, max_length=256)

    @field_validator("lecture_ids")
    @classmethod
    def unique_lecture_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("课次编号必须大于 0")
        return list(dict.fromkeys(values))

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value and value.strip() else None


class AssistantThreadResp(BaseModel):
    id: int
    course_id: Optional[int] = None
    lecture_ids: list[int] = Field(default_factory=list)
    title: str
    summary: Optional[str] = None
    last_message_preview: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class AssistantMessageResp(BaseModel):
    id: int
    role: str
    content: str
    citations: list[dict] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class AssistantThreadDetailResp(AssistantThreadResp):
    messages: list[AssistantMessageResp] = Field(default_factory=list)


class AssistantAskThreadReq(BaseModel):
    question: str = Field("", max_length=500)
    hint: Optional[str] = Field(
        None,
        description="强制工具意图：search_notebook|list_assignments|breakdown_assignment|get_notebook_overview",
    )
    assignment_id: Optional[str] = Field(
        None, max_length=32, description="作业编号，如 L12A0",
    )
    image_url: Optional[str] = Field(None, max_length=512)
    image_ocr: Optional[str] = Field(None, max_length=2000)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("hint")
    @classmethod
    def normalize_hint(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        allowed = {
            "search_notebook",
            "list_assignments",
            "breakdown_assignment",
            "get_notebook_overview",
        }
        if value not in allowed:
            raise ValueError("不支持的 hint")
        return value

    @field_validator("assignment_id")
    @classmethod
    def normalize_assignment_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("image_url")
    @classmethod
    def normalize_image_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not value.startswith("/uploads/assistant/"):
            raise ValueError("截图地址无效")
        return value

    @field_validator("image_ocr")
    @classmethod
    def normalize_image_ocr(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def require_question_or_image(self):
        if not self.question and not self.image_url and not self.image_ocr:
            raise ValueError("请输入问题或上传截图")
        return self


class AssistantScreenshotResp(BaseModel):
    url: str
    ocr_text: str = ""
    ocr_confidence: float = 0.0
    ocr_status: str = "ready"
    error_message: Optional[str] = None


class AssistantAskThreadResp(BaseModel):
    answer: str
    citations: list[dict] = Field(default_factory=list)
    provider: str = "extractive"
    thread: AssistantThreadResp

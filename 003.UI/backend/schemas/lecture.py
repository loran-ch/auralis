"""LiveTrans Voice — 课堂/转录/收藏 Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class StartLectureReq(BaseModel):
    course_name: str = Field(default="未命名课程", max_length=256)
    source_lang: str = Field(default="de")
    target_lang: str = Field(default="zh-CN")


class LectureResp(BaseModel):
    id: int
    course_name: str
    source_lang: str
    target_lang: str
    status: str
    duration_seconds: int = 0
    sentence_count: int = 0
    bookmark_count: int = 0
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
    model_config = {"from_attributes": True}


class BookmarkReq(BaseModel):
    transcription_id: int = Field(..., gt=0)
    tag: str = Field(default="important", pattern="^(important|question|exam|definition)$")


class BookmarkResp(BaseModel):
    bookmark_id: int
    tag: str
    source_text: str
    translated_text: str

"""LiveTrans Voice — 功能说明 Schema"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GuideItem(BaseModel):
    icon: str = Field("info", max_length=48)
    title: str = Field(..., min_length=1, max_length=64)
    body: str = Field(..., min_length=1, max_length=300)


class GuideResp(BaseModel):
    slug: str
    title: str
    subtitle: str = ""
    items: list[GuideItem] = Field(default_factory=list)
    footer_hint: str = ""
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


class GuideUpdateReq(BaseModel):
    title: str = Field(..., min_length=1, max_length=128)
    subtitle: str = Field("", max_length=512)
    items: list[GuideItem] = Field(..., min_length=1, max_length=8)
    footer_hint: str = Field("", max_length=256)

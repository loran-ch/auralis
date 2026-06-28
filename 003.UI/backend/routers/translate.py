"""LiveTrans Voice — 翻译路由"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from services.translator import translate

router = APIRouter(prefix="/api/translate", tags=["翻译"])


class TranslateReq(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    source: str = Field(default="en")
    target: str = Field(default="zh-CN")


class TranslateResp(BaseModel):
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str


@router.post("", response_model=TranslateResp)
def api_translate(req: TranslateReq):
    result = translate(req.text, req.source, req.target)
    return TranslateResp(
        source_text=req.text,
        translated_text=result,
        source_lang=req.source,
        target_lang=req.target,
    )

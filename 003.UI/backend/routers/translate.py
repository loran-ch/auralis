"""LiveTrans Voice — 翻译路由"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from models.user import User
from routers.auth import get_current_user
from services.translator import translate_with_context

router = APIRouter(prefix="/api/translate", tags=["翻译"])


class TranslateReq(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    source: str = Field(default="en", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    target: str = Field(default="zh-CN", pattern=r"^[a-z]{2}(?:-[A-Z]{2})?$")
    context: list[str] = Field(default_factory=list, max_length=5)


class TranslateResp(BaseModel):
    source_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    success: bool
    provider: str
    warning: str | None = None
    context_applied: bool = False


@router.post("", response_model=TranslateResp)
def api_translate(req: TranslateReq, user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(401, "请先登录")
    result = translate_with_context(req.text, req.context, req.source, req.target)
    return TranslateResp(
        source_text=req.text,
        translated_text=result["text"],
        source_lang=req.source,
        target_lang=req.target,
        success=result["success"],
        provider=result["provider"],
        warning=result["warning"],
        context_applied=result["context_applied"],
    )

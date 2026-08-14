"""公开读取前台功能说明。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas.guide import GuideResp
from services.guide import RECORDER_FEATURES_SLUG, get_guide

router = APIRouter(prefix="/api/guides", tags=["功能说明"])


@router.get("/{slug}", response_model=GuideResp)
def api_get_guide(slug: str = RECORDER_FEATURES_SLUG, db: Session = Depends(get_db)):
    return GuideResp(**get_guide(db, slug))

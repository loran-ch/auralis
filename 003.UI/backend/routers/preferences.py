"""语言、用户设置和课程表路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from routers.auth import get_current_user
from schemas.auth import MsgResp
from schemas.preferences import (
    CourseScheduleCreate,
    CourseScheduleResp,
    CourseScheduleUpdate,
    LanguageResp,
    UserSettingsResp,
    UserSettingsUpdate,
)
from services.preferences import (
    create_schedule,
    deactivate_schedule,
    get_or_create_settings,
    list_languages,
    list_schedules,
    update_schedule,
    update_settings,
)


router = APIRouter(prefix="/api", tags=["偏好与课程表"])


def _require_user(user: Optional[User]) -> User:
    if not user:
        raise HTTPException(401, "请先登录")
    return user


@router.get("/languages", response_model=list[LanguageResp])
def api_languages(db: Session = Depends(get_db)):
    return [LanguageResp.model_validate(item) for item in list_languages(db)]


@router.get("/settings", response_model=UserSettingsResp)
def api_get_settings(user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    user = _require_user(user)
    return UserSettingsResp.model_validate(get_or_create_settings(db, user.id))


@router.put("/settings", response_model=UserSettingsResp)
def api_update_settings(request: UserSettingsUpdate,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    user = _require_user(user)
    try:
        settings = update_settings(db, user.id, request)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return UserSettingsResp.model_validate(settings)


@router.get("/schedules", response_model=list[CourseScheduleResp])
def api_list_schedules(
    day_of_week: Optional[int] = Query(None, ge=1, le=7),
    include_inactive: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = _require_user(user)
    return [CourseScheduleResp.model_validate(item) for item in list_schedules(
        db, user.id, day_of_week, include_inactive
    )]


@router.post("/schedules", response_model=CourseScheduleResp, status_code=201)
def api_create_schedule(request: CourseScheduleCreate,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    user = _require_user(user)
    try:
        schedule = create_schedule(db, user.id, request)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return CourseScheduleResp.model_validate(schedule)


@router.put("/schedules/{schedule_id}", response_model=CourseScheduleResp)
def api_update_schedule(schedule_id: int, request: CourseScheduleUpdate,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    user = _require_user(user)
    try:
        schedule = update_schedule(db, user.id, schedule_id, request)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not schedule:
        raise HTTPException(404, "课程不存在")
    return CourseScheduleResp.model_validate(schedule)


@router.delete("/schedules/{schedule_id}", response_model=MsgResp)
def api_delete_schedule(schedule_id: int, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    user = _require_user(user)
    if not deactivate_schedule(db, user.id, schedule_id):
        raise HTTPException(404, "课程不存在")
    return MsgResp(message="课程已停用")

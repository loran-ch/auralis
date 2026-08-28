"""课程中心路由。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.course import Course
from models.preferences import CourseSchedule
from models.user import User
from routers.auth import get_current_user
from schemas.auth import MsgResp
from schemas.courses import (CourseCreate, CourseOverviewResp, CourseResp,
                             CourseScheduleAttachReq, CourseUpdate)
from schemas.preferences import CourseScheduleCreate as LegacyCourseScheduleCreate, CourseScheduleResp
from services.courses import (
    can_manage_course,
    course_for_current_schedule,
    course_to_resp,
    create_course,
    deactivate_course,
    delete_course,
    get_owned_course,
    get_readable_course,
    get_course_overview,
    list_courses,
    list_public_courses,
    update_course,
)
from services.preferences import create_schedule

router = APIRouter(prefix="/api/courses", tags=["课程中心"])


def _user_or_401(user: Optional[User]) -> User:
    if not user:
        raise HTTPException(401, "请先登录")
    return user


def _course_resp(course, viewer: User, db: Session) -> CourseResp:
    owner = db.query(User).filter(User.id == course.user_id).first()
    return CourseResp.model_validate(course_to_resp(course, viewer, owner))


@router.get("/recommendation/now", response_model=Optional[CourseResp])
def api_now_recommendation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _user_or_401(user)
    course = course_for_current_schedule(db, user.id)
    return _course_resp(course, user, db) if course else None


@router.get("/public", response_model=list[CourseResp])
def api_list_public_courses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _user_or_401(user)
    rows = list_public_courses(db)
    return [
        CourseResp.model_validate(course_to_resp(course, user, owner))
        for course, owner in rows
    ]


@router.get("", response_model=list[CourseResp])
def api_list_courses(include_inactive: bool = False, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    user = _user_or_401(user)
    return [
        _course_resp(course, user, db)
        for course in list_courses(db, user.id, include_inactive=include_inactive)
    ]


@router.post("", response_model=CourseResp, status_code=201)
def api_create_course(request: CourseCreate, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    user = _user_or_401(user)
    try:
        course = create_course(db, user.id, request)
        return _course_resp(course, user, db)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{course_id}", response_model=CourseResp)
def api_get_course(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _user_or_401(user)
    course = get_readable_course(db, user, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    return _course_resp(course, user, db)


@router.patch("/{course_id}", response_model=CourseResp)
def api_update_course(course_id: int, request: CourseUpdate, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    user = _user_or_401(user)
    try:
        course = update_course(db, user, course_id, request)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not course:
        raise HTTPException(404, "课程不存在")
    return _course_resp(course, user, db)


@router.delete("/{course_id}", response_model=MsgResp)
def api_deactivate_course(course_id: int, permanent: bool = Query(False),
                          user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    user = _user_or_401(user)
    if permanent:
        if not delete_course(db, user, course_id):
            raise HTTPException(404, "课程不存在")
        return MsgResp(message="课程已永久删除；课堂记录已保留为未归类，关联课表已停用")
    if not deactivate_course(db, user, course_id):
        raise HTTPException(404, "课程不存在")
    return MsgResp(message="课程已归档，既有课堂记录会继续保留")


@router.get("/{course_id}/overview", response_model=CourseOverviewResp)
def api_course_overview(course_id: int, user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    user = _user_or_401(user)
    course = get_readable_course(db, user, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    data = get_course_overview(db, user, course)
    return CourseOverviewResp(
        course=CourseResp.model_validate(data["course"]),
        lecture_count=data["lecture_count"],
        completed_lecture_count=data["completed_lecture_count"],
        total_duration_seconds=data["total_duration_seconds"],
        schedules=[CourseScheduleResp.model_validate(row) for row in data["schedules"]],
        recent_lectures=data["recent_lectures"],
        can_manage=data["can_manage"],
    )


@router.get("/{course_id}/schedules", response_model=list[CourseScheduleResp])
def api_course_schedules(course_id: int, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    user = _user_or_401(user)
    course = get_owned_course(db, user.id, course_id)
    if not course:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course or not can_manage_course(course, user):
            raise HTTPException(404, "课程不存在")
    owner_id = int(course.user_id)
    rows = db.query(CourseSchedule).filter(
        CourseSchedule.user_id == owner_id, CourseSchedule.course_id == course_id
    ).order_by(CourseSchedule.day_of_week, CourseSchedule.start_time).all()
    return [CourseScheduleResp.model_validate(row) for row in rows]


@router.post("/{course_id}/schedules", response_model=CourseScheduleResp, status_code=201)
def api_create_course_schedule(course_id: int, request: CourseScheduleAttachReq,
                               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _user_or_401(user)
    course = get_owned_course(db, user.id, course_id, include_inactive=False)
    if not course:
        raise HTTPException(404, "课程不存在或已归档")
    schedule_request = LegacyCourseScheduleCreate(
        course_id=course.id,
        course_name=course.name,
        source_lang=course.source_lang,
        target_lang=course.target_lang,
        room=course.room,
        professor_name=course.professor_name,
        day_of_week=request.day_of_week,
        start_time=request.start_time,
        end_time=request.end_time,
    )
    try:
        schedule = create_schedule(db, user.id, schedule_request)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return CourseScheduleResp.model_validate(schedule)

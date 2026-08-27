"""用户偏好、统计和课程表业务逻辑。"""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.lecture import Bookmark, Lecture
from models.course import Course
from models.preferences import CourseSchedule, Language, UserSettings, UserStats
from schemas.preferences import CourseScheduleCreate, CourseScheduleUpdate, UserSettingsUpdate


def language_exists(db: Session, code: str, *, allow_auto: bool = False) -> bool:
    if allow_auto and code == "auto":
        return True
    return db.query(Language.code).filter(
        Language.code == code,
        Language.is_active == True,
    ).first() is not None


def list_languages(db: Session) -> list[Language]:
    return db.query(Language).filter(
        Language.is_active == True,
    ).order_by(Language.sort_order, Language.code).all()


def get_or_create_settings(db: Session, user_id: int) -> UserSettings:
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if settings:
        return settings
    settings = UserSettings(user_id=user_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def update_settings(db: Session, user_id: int,
                    request: UserSettingsUpdate) -> UserSettings:
    settings = get_or_create_settings(db, user_id)
    values = request.model_dump(exclude_unset=True, exclude_none=True)
    source = values.get("default_source_lang")
    target = values.get("default_target_lang")
    if source and not language_exists(db, source, allow_auto=True):
        raise ValueError("不支持的源语言")
    if target and not language_exists(db, target):
        raise ValueError("不支持的目标语言")
    for field, value in values.items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings


def _calculate_streak(lecture_dates: list[date]) -> int:
    if not lecture_dates:
        return 0
    today = date.today()
    newest = lecture_dates[0]
    if newest == today:
        expected = today
    elif newest == today - timedelta(days=1):
        expected = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    for lecture_date in lecture_dates:
        if lecture_date == expected:
            streak += 1
            expected -= timedelta(days=1)
        elif lecture_date < expected:
            break
    return streak


def refresh_user_stats(db: Session, user_id: int) -> dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_start_dt = datetime.combine(week_start, datetime.min.time())

    total_seconds, lecture_count = db.query(
        func.coalesce(func.sum(Lecture.duration_seconds), 0),
        func.count(Lecture.id),
    ).filter(
        Lecture.user_id == user_id,
        Lecture.status == "completed",
    ).one()
    weekly_seconds = db.query(
        func.coalesce(func.sum(Lecture.duration_seconds), 0)
    ).filter(
        Lecture.user_id == user_id,
        Lecture.status == "completed",
        Lecture.lecture_date >= week_start,
    ).scalar() or 0
    bookmark_count = db.query(func.count(Bookmark.id)).filter(
        Bookmark.user_id == user_id,
    ).scalar() or 0
    weekly_bookmarks = db.query(func.count(Bookmark.id)).filter(
        Bookmark.user_id == user_id,
        Bookmark.created_at >= week_start_dt,
    ).scalar() or 0
    lecture_dates = [row[0] for row in db.query(Lecture.lecture_date).filter(
        Lecture.user_id == user_id,
        Lecture.status == "completed",
        Lecture.lecture_date.isnot(None),
    ).distinct().order_by(Lecture.lecture_date.desc()).all()]
    streak = _calculate_streak(lecture_dates)

    cached = db.query(UserStats).filter(UserStats.user_id == user_id).first()
    if not cached:
        cached = UserStats(user_id=user_id)
        db.add(cached)
    cached.total_record_seconds = int(total_seconds or 0)
    cached.total_lecture_count = int(lecture_count or 0)
    cached.total_bookmark_count = int(bookmark_count)
    cached.weekly_record_seconds = int(weekly_seconds)
    cached.weekly_bookmark_count = int(weekly_bookmarks)
    cached.current_streak_days = streak
    db.commit()

    return {
        "total_seconds": cached.total_record_seconds,
        "total_hours": round(cached.total_record_seconds / 3600, 1),
        "lecture_count": cached.total_lecture_count,
        "bookmark_count": cached.total_bookmark_count,
        "weekly_record_seconds": cached.weekly_record_seconds,
        "weekly_record_hours": round(cached.weekly_record_seconds / 3600, 1),
        "weekly_bookmark_count": cached.weekly_bookmark_count,
        "current_streak_days": cached.current_streak_days,
        "exam_mastery_improve": cached.exam_mastery_improve or 0,
    }


def list_schedules(db: Session, user_id: int,
                   day_of_week: Optional[int] = None,
                   include_inactive: bool = False) -> list[CourseSchedule]:
    query = db.query(CourseSchedule).filter(CourseSchedule.user_id == user_id)
    if day_of_week:
        query = query.filter(CourseSchedule.day_of_week == day_of_week)
    if not include_inactive:
        query = query.filter(CourseSchedule.is_active == True)
    return query.order_by(CourseSchedule.day_of_week, CourseSchedule.start_time).all()


def _ensure_schedule_languages(db: Session, source: str, target: str) -> None:
    if not language_exists(db, source):
        raise ValueError("不支持的源语言")
    if not language_exists(db, target):
        raise ValueError("不支持的目标语言")


def _has_schedule_conflict(db: Session, user_id: int, day_of_week: int,
                           start_time, end_time,
                           exclude_id: Optional[int] = None) -> bool:
    query = db.query(CourseSchedule.id).filter(
        CourseSchedule.user_id == user_id,
        CourseSchedule.day_of_week == day_of_week,
        CourseSchedule.is_active == True,
        CourseSchedule.start_time < end_time,
        CourseSchedule.end_time > start_time,
    )
    if exclude_id:
        query = query.filter(CourseSchedule.id != exclude_id)
    return query.first() is not None


def create_schedule(db: Session, user_id: int,
                    request: CourseScheduleCreate) -> CourseSchedule:
    _ensure_schedule_languages(db, request.source_lang, request.target_lang)
    if request.course_id and not db.query(Course.id).filter(
        Course.id == request.course_id, Course.user_id == user_id
    ).first():
        raise ValueError("关联课程不存在")
    if _has_schedule_conflict(
        db, user_id, request.day_of_week, request.start_time, request.end_time
    ):
        raise RuntimeError("课程时间与现有课程冲突")
    schedule = CourseSchedule(user_id=user_id, **request.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def update_schedule(db: Session, user_id: int, schedule_id: int,
                    request: CourseScheduleUpdate) -> Optional[CourseSchedule]:
    schedule = db.query(CourseSchedule).filter(
        CourseSchedule.id == schedule_id,
        CourseSchedule.user_id == user_id,
    ).first()
    if not schedule:
        return None
    values = request.model_dump(exclude_unset=True)
    course_id = values.get("course_id")
    if course_id and not db.query(Course.id).filter(
        Course.id == course_id, Course.user_id == user_id
    ).first():
        raise ValueError("关联课程不存在")
    source = values.get("source_lang", schedule.source_lang)
    target = values.get("target_lang", schedule.target_lang)
    _ensure_schedule_languages(db, source, target)
    day = values.get("day_of_week", schedule.day_of_week)
    start = values.get("start_time", schedule.start_time)
    end = values.get("end_time", schedule.end_time)
    if start >= end:
        raise ValueError("结束时间必须晚于开始时间")
    if values.get("is_active", schedule.is_active) and _has_schedule_conflict(
        db, user_id, day, start, end, exclude_id=schedule.id
    ):
        raise RuntimeError("课程时间与现有课程冲突")
    for field, value in values.items():
        if isinstance(value, str):
            value = value.strip()
            if field == "course_name" and not value:
                raise ValueError("课程名称不能为空")
            value = value or None
        setattr(schedule, field, value)
    db.commit()
    db.refresh(schedule)
    return schedule


def deactivate_schedule(db: Session, user_id: int, schedule_id: int) -> bool:
    schedule = db.query(CourseSchedule).filter(
        CourseSchedule.id == schedule_id,
        CourseSchedule.user_id == user_id,
    ).first()
    if not schedule:
        return False
    schedule.is_active = False
    db.commit()
    return True

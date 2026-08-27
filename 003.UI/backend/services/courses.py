"""课程中心业务逻辑。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.course import Course
from models.lecture import Lecture
from models.preferences import CourseSchedule
from models.user import User
from schemas.courses import CourseCreate, CourseUpdate
from services.preferences import language_exists


def _ensure_languages(db: Session, source_lang: str, target_lang: str) -> None:
    if not language_exists(db, source_lang):
        raise ValueError("不支持的源语言")
    if not language_exists(db, target_lang):
        raise ValueError("不支持的目标语言")


def is_admin_user(user: User) -> bool:
    return getattr(user, "role", None) in {"admin", "super_admin"}


def course_to_resp(course: Course, viewer: User, owner: Optional[User] = None) -> dict:
    owner_id = int(course.user_id)
    is_owner = owner_id == int(viewer.id)
    return {
        "id": course.id,
        "name": course.name,
        "professor_name": course.professor_name,
        "room": course.room,
        "term": course.term,
        "source_lang": course.source_lang,
        "target_lang": course.target_lang,
        "translation_enabled": bool(course.translation_enabled),
        "color": course.color or "#2563EB",
        "is_active": bool(course.is_active),
        "is_public": bool(getattr(course, "is_public", False)),
        "owner_id": owner_id,
        "owner_nickname": (owner.nickname if owner else None),
        "is_owner": is_owner,
        "created_at": course.created_at,
        "updated_at": course.updated_at,
    }


def get_owned_course(db: Session, user_id: int, course_id: int,
                     *, include_inactive: bool = True) -> Optional[Course]:
    query = db.query(Course).filter(Course.id == course_id, Course.user_id == user_id)
    if not include_inactive:
        query = query.filter(Course.is_active == True)
    return query.first()


def get_course(db: Session, user_id: int, course_id: int,
               *, include_inactive: bool = True) -> Optional[Course]:
    """兼容旧调用：仅返回当前用户拥有的课程。"""
    return get_owned_course(db, user_id, course_id, include_inactive=include_inactive)


def get_readable_course(db: Session, viewer: User, course_id: int) -> Optional[Course]:
    """课主可读任意自己的课；其他用户仅可读公开且活跃的课。"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        return None
    if int(course.user_id) == int(viewer.id):
        return course
    if bool(getattr(course, "is_public", False)) and bool(course.is_active):
        return course
    return None


def list_courses(db: Session, user_id: int, *, include_inactive: bool = False) -> list[Course]:
    query = db.query(Course).filter(Course.user_id == user_id)
    if not include_inactive:
        query = query.filter(Course.is_active == True)
    return query.order_by(Course.is_active.desc(), Course.updated_at.desc(), Course.id.desc()).all()


def list_public_courses(db: Session) -> list[tuple[Course, Optional[User]]]:
    rows = (
        db.query(Course, User)
        .outerjoin(User, User.id == Course.user_id)
        .filter(Course.is_public == True, Course.is_active == True)
        .order_by(Course.updated_at.desc(), Course.id.desc())
        .all()
    )
    return [(course, owner) for course, owner in rows]


def create_course(db: Session, user_id: int, request: CourseCreate) -> Course:
    _ensure_languages(db, request.source_lang, request.target_lang)
    course = Course(user_id=user_id, **request.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def update_course(db: Session, user: User, course_id: int,
                  request: CourseUpdate) -> Optional[Course]:
    course = get_owned_course(db, user.id, course_id)
    if not course:
        return None
    values = request.model_dump(exclude_unset=True)
    if "is_public" in values:
        if not is_admin_user(user):
            raise PermissionError("仅管理员可公开课程")
        if not bool(course.is_active) and values["is_public"]:
            raise ValueError("已归档课程不能设为公开")
    source = values.get("source_lang", course.source_lang)
    target = values.get("target_lang", course.target_lang)
    _ensure_languages(db, source, target)
    for field, value in values.items():
        if field in {"professor_name", "room", "term"} and value == "":
            value = None
        setattr(course, field, value)
    # 归档时自动取消公开，避免目录残留。
    if "is_active" in values and values["is_active"] is False:
        course.is_public = False
    db.commit()
    db.refresh(course)
    return course


def deactivate_course(db: Session, user_id: int, course_id: int) -> bool:
    course = get_owned_course(db, user_id, course_id)
    if not course:
        return False
    course.is_active = False
    course.is_public = False
    # 归档课程后不应继续出现在“当前上课推荐”中，也不能占用排课冲突检测。
    db.query(CourseSchedule).filter(
        CourseSchedule.user_id == user_id,
        CourseSchedule.course_id == course_id,
    ).update({CourseSchedule.is_active: False}, synchronize_session=False)
    db.commit()
    return True


def delete_course(db: Session, user_id: int, course_id: int) -> bool:
    """永久删除课程实体，但不删除已经产生的课堂学习资料。"""
    course = get_owned_course(db, user_id, course_id)
    if not course:
        return False
    # 保留课表审计信息但让其不再参与推荐和排课冲突；课堂的外键由数据库置空。
    db.query(CourseSchedule).filter(
        CourseSchedule.user_id == user_id,
        CourseSchedule.course_id == course_id,
    ).update({CourseSchedule.is_active: False}, synchronize_session=False)
    db.delete(course)
    db.commit()
    return True


def get_course_overview(db: Session, viewer: User, course: Course) -> dict:
    is_owner = int(course.user_id) == int(viewer.id)
    lecture_query = db.query(Lecture).filter(Lecture.course_id == course.id)
    if is_owner:
        lecture_query = lecture_query.filter(Lecture.user_id == viewer.id)
    else:
        # 公开课访客只看课主的已完成课次。
        lecture_query = lecture_query.filter(
            Lecture.user_id == course.user_id,
            Lecture.status == "completed",
        )

    lecture_count, completed_count, duration = db.query(
        func.count(Lecture.id),
        func.coalesce(func.sum(Lecture.status == "completed"), 0),
        func.coalesce(func.sum(Lecture.duration_seconds), 0),
    ).filter(
        Lecture.course_id == course.id,
        Lecture.user_id == (viewer.id if is_owner else course.user_id),
        *([] if is_owner else [Lecture.status == "completed"]),
    ).one()

    schedules = []
    if is_owner:
        schedules = db.query(CourseSchedule).filter(
            CourseSchedule.user_id == viewer.id,
            CourseSchedule.course_id == course.id,
            CourseSchedule.is_active == True,
        ).order_by(CourseSchedule.day_of_week, CourseSchedule.start_time).all()

    lectures = lecture_query.order_by(
        Lecture.lecture_date.desc(), Lecture.started_at.desc(), Lecture.id.desc()
    ).limit(20).all()

    owner = db.query(User).filter(User.id == course.user_id).first()
    return {
        "course": course_to_resp(course, viewer, owner),
        "lecture_count": int(lecture_count or 0),
        "completed_lecture_count": int(completed_count or 0),
        "total_duration_seconds": int(duration or 0),
        "schedules": schedules,
        "recent_lectures": lectures,
        "can_manage": is_owner,
    }


def course_for_current_schedule(db: Session, user_id: int,
                                now: Optional[datetime] = None) -> Optional[Course]:
    now = now or datetime.now()
    weekday = now.isoweekday()
    current_time = now.time()
    schedule = db.query(CourseSchedule).filter(
        CourseSchedule.user_id == user_id,
        CourseSchedule.course_id.isnot(None),
        CourseSchedule.is_active == True,
        CourseSchedule.day_of_week == weekday,
        CourseSchedule.start_time <= current_time,
        CourseSchedule.end_time >= current_time,
    ).order_by(CourseSchedule.start_time.desc()).first()
    if not schedule:
        return None
    return get_owned_course(db, user_id, schedule.course_id, include_inactive=False)


def lecture_on_public_course(db: Session, lecture: Lecture) -> bool:
    if not lecture.course_id or lecture.status != "completed":
        return False
    course = db.query(Course).filter(Course.id == lecture.course_id).first()
    return bool(
        course
        and course.is_active
        and getattr(course, "is_public", False)
        and int(course.user_id) == int(lecture.user_id)
    )

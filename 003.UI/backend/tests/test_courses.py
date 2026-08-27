from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from schemas.courses import CourseCreate, CourseUpdate
from schemas.lecture import StartLectureReq
from schemas.preferences import CourseScheduleCreate
from services import courses as course_service


def test_course_create_normalizes_optional_fields():
    course = CourseCreate(
        name="  Python 程序设计  ",
        professor_name="  王老师  ",
        room="  A-301 ",
    )

    assert course.name == "Python 程序设计"
    assert course.professor_name == "王老师"
    assert course.room == "A-301"
    assert course.translation_enabled is False


def test_start_lecture_accepts_course_and_uses_course_default_mode():
    request = StartLectureReq(course_id=42, course_name="临时名称")

    assert request.course_id == 42
    assert request.translation_enabled is None


def test_schedule_can_link_to_course():
    schedule = CourseScheduleCreate(
        course_id=42,
        course_name="Python 程序设计",
        day_of_week=1,
        start_time="08:00",
        end_time="09:40",
    )

    assert schedule.course_id == 42


def test_course_update_accepts_is_public():
    payload = CourseUpdate(is_public=True)
    assert payload.is_public is True


def test_non_admin_cannot_publish_course():
    db = MagicMock()
    viewer = SimpleNamespace(id=2, role="user")
    course = SimpleNamespace(
        id=11, user_id=2, is_active=True, is_public=False,
        source_lang="en", target_lang="zh-CN",
    )
    with patch.object(course_service, "get_owned_course", return_value=course), \
         patch.object(course_service, "_ensure_languages"):
        try:
            course_service.update_course(db, viewer, 11, CourseUpdate(is_public=True))
            assert False, "expected PermissionError"
        except PermissionError as exc:
            assert "管理员" in str(exc)


def test_admin_can_publish_owned_course():
    db = MagicMock()
    viewer = SimpleNamespace(id=4, role="admin")
    course = SimpleNamespace(
        id=11, user_id=4, is_active=True, is_public=False,
        source_lang="en", target_lang="zh-CN",
    )
    with patch.object(course_service, "get_owned_course", return_value=course), \
         patch.object(course_service, "_ensure_languages"):
        updated = course_service.update_course(db, viewer, 11, CourseUpdate(is_public=True))
    assert updated is course
    assert course.is_public is True
    db.commit.assert_called()


def test_readable_course_allows_public_for_other_users():
    db = MagicMock()
    viewer = SimpleNamespace(id=9, role="user")
    public_course = SimpleNamespace(id=11, user_id=4, is_active=True, is_public=True)
    db.query.return_value.filter.return_value.first.return_value = public_course
    assert course_service.get_readable_course(db, viewer, 11) is public_course


def test_readable_course_hides_private_from_others():
    db = MagicMock()
    viewer = SimpleNamespace(id=9, role="user")
    private_course = SimpleNamespace(id=11, user_id=4, is_active=True, is_public=False)
    db.query.return_value.filter.return_value.first.return_value = private_course
    assert course_service.get_readable_course(db, viewer, 11) is None


def test_deactivate_clears_public_flag():
    db = MagicMock()
    course = SimpleNamespace(id=11, user_id=4, is_active=True, is_public=True)
    with patch.object(course_service, "get_owned_course", return_value=course):
        assert course_service.deactivate_course(db, 4, 11) is True
    assert course.is_active is False
    assert course.is_public is False

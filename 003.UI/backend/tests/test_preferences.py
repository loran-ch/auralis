from datetime import date, time, timedelta
import unittest

from pydantic import ValidationError

from schemas.preferences import CourseScheduleCreate, UserSettingsUpdate
from services.preferences import _calculate_streak


class PreferencesSchemaTests(unittest.TestCase):
    def test_schedule_requires_valid_time_range(self):
        schedule = CourseScheduleCreate(
            course_name=" 计算机科学 ",
            source_lang="en",
            target_lang="zh-CN",
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(10, 30),
        )
        self.assertEqual(schedule.course_name, "计算机科学")

        with self.assertRaises(ValidationError):
            CourseScheduleCreate(
                course_name="无效课程",
                day_of_week=1,
                start_time=time(10, 0),
                end_time=time(9, 0),
            )

    def test_settings_reject_unknown_values(self):
        with self.assertRaises(ValidationError):
            UserSettingsUpdate(dark_mode="midnight")


class UserStatsTests(unittest.TestCase):
    def test_streak_accepts_today_or_yesterday_as_latest_day(self):
        today = date.today()
        self.assertEqual(_calculate_streak([
            today, today - timedelta(days=1), today - timedelta(days=2)
        ]), 3)
        self.assertEqual(_calculate_streak([
            today - timedelta(days=1), today - timedelta(days=2)
        ]), 2)
        self.assertEqual(_calculate_streak([today - timedelta(days=3)]), 0)


if __name__ == "__main__":
    unittest.main()

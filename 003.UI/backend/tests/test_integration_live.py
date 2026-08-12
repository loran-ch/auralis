"""可选的真实数据库/API 冒烟测试。

默认跳过，启动 8010 服务后设置 RUN_INTEGRATION=1 可执行。测试创建的数据会在结束时清理。
"""
import json
import os
import unittest
import urllib.error
import urllib.request
import uuid
from datetime import time

from config import ASR_API_URL
from database import SessionLocal
from models.preferences import CourseSchedule


@unittest.skipUnless(os.getenv("RUN_INTEGRATION") == "1", "需要显式启用真实 API 联调")
class LiveApiIntegrationTests(unittest.TestCase):
    base_url = os.getenv("INTEGRATION_BASE_URL", "http://127.0.0.1:8010")
    phone = os.getenv("INTEGRATION_PHONE", "13800000002")
    password = os.getenv("INTEGRATION_PASSWORD", "123456")

    def setUp(self):
        self.access_token = None
        self.refresh_token = None
        self.schedule_id = None
        self.user_id = None
        status, data = self.call(
            "/api/auth/login",
            method="POST",
            payload={"account": self.phone, "password": self.password},
            authenticated=False,
        )
        self.assertEqual(status, 200, data)
        self.access_token = data["tokens"]["access_token"]
        self.refresh_token = data["tokens"]["refresh_token"]
        self.user_id = data["user"]["id"]

    def tearDown(self):
        if self.schedule_id:
            with SessionLocal() as db:
                db.query(CourseSchedule).filter(
                    CourseSchedule.id == self.schedule_id,
                    CourseSchedule.user_id == self.user_id,
                ).delete(synchronize_session=False)
                db.commit()

    def call(self, path, *, method="GET", payload=None, authenticated=True,
             raw_body=None, content_type="application/json"):
        body = raw_body
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = content_type
        if authenticated and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        request = urllib.request.Request(
            self.base_url + path, data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            try:
                raw = exc.read()
                return exc.code, json.loads(raw) if raw else None
            finally:
                exc.close()

    @staticmethod
    def free_schedule_slot(items):
        occupied = {day: [] for day in range(1, 8)}
        for item in items:
            if not item.get("is_active", True):
                continue
            start = time.fromisoformat(item["start_time"])
            end = time.fromisoformat(item["end_time"])
            occupied[item["day_of_week"]].append((start, end))
        for day in range(1, 8):
            for hour in range(0, 24):
                start = time(hour, 0)
                end = time(hour, 10)
                if not any(existing_start < end and existing_end > start
                           for existing_start, existing_end in occupied[day]):
                    return day, start.isoformat(), end.isoformat()
        raise AssertionError("没有可用于冒烟测试的课程时间")

    def test_complete_business_flow(self):
        lecture_id = None
        try:
            status, ready = self.call("/health/ready", authenticated=False)
            self.assertEqual((status, ready["status"]), (200, "ready"))

            status, languages = self.call("/api/languages", authenticated=False)
            self.assertEqual(status, 200)
            self.assertGreaterEqual(len(languages), 2)
            for path in ("/api/auth/me", "/api/settings", "/api/auth/stats"):
                status, response = self.call(path)
                self.assertEqual(status, 200, response)

            status, schedules = self.call("/api/schedules?include_inactive=true")
            self.assertEqual(status, 200, schedules)
            day, start, end = self.free_schedule_slot(schedules)
            status, schedule = self.call("/api/schedules", method="POST", payload={
                "course_name": "__integration_smoke__",
                "source_lang": "en",
                "target_lang": "zh-CN",
                "day_of_week": day,
                "start_time": start,
                "end_time": end,
            })
            self.assertEqual(status, 201, schedule)
            self.schedule_id = schedule["id"]
            status, schedule = self.call(
                f"/api/schedules/{self.schedule_id}", method="PUT",
                payload={"room": "Smoke Room"},
            )
            self.assertEqual((status, schedule["room"]), (200, "Smoke Room"))
            status, _ = self.call(f"/api/schedules/{self.schedule_id}", method="DELETE")
            self.assertEqual(status, 200)

            status, lecture = self.call("/api/lectures/start", method="POST", payload={
                "course_name": "__integration_smoke__",
                "source_lang": "en",
                "target_lang": "zh-CN",
            })
            self.assertEqual(status, 200, lecture)
            lecture_id = lecture["id"]
            for action, expected in (("pause", "paused"), ("resume", "recording")):
                status, lecture = self.call(
                    f"/api/lectures/{lecture_id}/{action}", method="POST"
                )
                self.assertEqual((status, lecture["status"]), (200, expected))

            status, translation = self.call("/api/translate", method="POST", payload={
                "text": "Good morning", "source": "en", "target": "zh-CN"
            })
            self.assertEqual(status, 200, translation)
            self.assertTrue(translation["translated_text"])
            self.assertTrue(translation["success"], translation)

            status, transcription = self.call(
                f"/api/lectures/{lecture_id}/transcribe/text",
                method="POST",
                payload={
                    "source_text": "Good morning",
                    "translated_text": translation["translated_text"],
                },
            )
            self.assertEqual(status, 200, transcription)
            status, bookmark = self.call("/api/bookmarks", method="POST", payload={
                "transcription_id": transcription["id"],
                "tag": "important",
                "note": "integration smoke",
            })
            self.assertEqual(status, 200, bookmark)
            status, bookmark = self.call(
                f"/api/bookmarks/{bookmark['bookmark_id']}", method="PATCH",
                payload={"tag": "exam", "note": "updated smoke"},
            )
            self.assertEqual((status, bookmark["tag"]), (200, "exam"))

            boundary = "----LiveTrans" + uuid.uuid4().hex
            audio = b"ID3\x04\x00\x00\x00\x00" + b"integration-mp3-segment-one"
            multipart = (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="file"; filename="smoke.mp3"\r\n'
                "Content-Type: audio/mpeg\r\n\r\n"
            ).encode() + audio + f"\r\n--{boundary}--\r\n".encode()
            status, lecture = self.call(
                f"/api/lectures/{lecture_id}/audio", method="POST",
                raw_body=multipart,
                content_type=f"multipart/form-data; boundary={boundary}",
            )
            self.assertEqual(status, 200, lecture)
            self.assertTrue(lecture["audio_url"])
            first_size = lecture["audio_size_bytes"]

            boundary = "----LiveTrans" + uuid.uuid4().hex
            second_audio = b"ID3\x04\x00\x00\x00\x00" + b"integration-mp3-segment-two"
            multipart = (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="append"\r\n\r\n'
                "true\r\n"
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="file"; filename="smoke-2.mp3"\r\n'
                "Content-Type: audio/mpeg\r\n\r\n"
            ).encode() + second_audio + f"\r\n--{boundary}--\r\n".encode()
            status, lecture = self.call(
                f"/api/lectures/{lecture_id}/audio", method="POST",
                raw_body=multipart,
                content_type=f"multipart/form-data; boundary={boundary}",
            )
            self.assertEqual(status, 200, lecture)
            self.assertEqual(lecture["audio_size_bytes"], first_size + len(second_audio))

            if not ASR_API_URL:
                boundary = "----LiveTrans" + uuid.uuid4().hex
                multipart = (
                    f"--{boundary}\r\n"
                    'Content-Disposition: form-data; name="file"; filename="asr.mp3"\r\n'
                    "Content-Type: audio/mpeg\r\n\r\n"
                ).encode() + second_audio + f"\r\n--{boundary}--\r\n".encode()
                status, response = self.call(
                    f"/api/lectures/{lecture_id}/transcribe/audio", method="POST",
                    raw_body=multipart,
                    content_type=f"multipart/form-data; boundary={boundary}",
                )
                self.assertEqual(status, 503, response)

            status, lecture = self.call(
                f"/api/lectures/{lecture_id}/stop", method="POST"
            )
            self.assertEqual((status, lecture["status"]), (200, "completed"))
            status, stats = self.call("/api/auth/stats")
            self.assertEqual(status, 200, stats)
            self.assertIn("weekly_bookmark_count", stats)
            status, result = self.call(
                f"/api/lectures/{lecture_id}", method="DELETE"
            )
            self.assertEqual(status, 200, result)
            lecture_id = None

            status, _ = self.call("/api/auth/logout", method="POST")
            self.assertEqual(status, 200)
            status, _ = self.call("/api/auth/me")
            self.assertEqual(status, 401)
            status, _ = self.call(
                "/api/auth/refresh", method="POST",
                payload={"refresh_token": self.refresh_token}, authenticated=False,
            )
            self.assertEqual(status, 401)
        finally:
            if lecture_id:
                self.call(f"/api/lectures/{lecture_id}", method="DELETE")


if __name__ == "__main__":
    unittest.main()

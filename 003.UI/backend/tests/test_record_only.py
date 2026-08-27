from schemas.lecture import StartLectureReq


def test_start_lecture_request_supports_record_only_mode():
    request = StartLectureReq(
        course_name="课堂录音",
        source_lang="en",
        target_lang="zh-CN",
        translation_enabled=False,
    )

    assert request.translation_enabled is False

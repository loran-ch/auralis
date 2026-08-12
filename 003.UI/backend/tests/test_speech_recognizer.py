from unittest.mock import patch

import pytest

from services import speech_recognizer


class _Response:
    ok = True
    status_code = 200

    def json(self):
        return {"text": "recognized sentence"}


def test_unconfigured_recognizer_fails_explicitly():
    with patch.object(speech_recognizer, "ASR_API_URL", ""):
        with pytest.raises(speech_recognizer.SpeechRecognitionUnavailable):
            speech_recognizer.recognize_speech(b"ID3-audio", ".mp3", "en")


def test_recognizer_parses_text_response_and_sends_language():
    with (
        patch.object(speech_recognizer, "ASR_API_URL", "https://asr.example.test"),
        patch.object(speech_recognizer, "ASR_API_KEY", "secret"),
        patch.object(speech_recognizer, "ASR_MODEL", "enterprise-asr"),
        patch.object(speech_recognizer.requests, "post", return_value=_Response()) as post,
    ):
        result = speech_recognizer.recognize_speech(b"ID3-audio", ".mp3", "en-US")
    assert result == "recognized sentence"
    request = post.call_args.kwargs
    assert request["headers"]["Authorization"] == "Bearer secret"
    assert request["data"]["language"] == "en"
    assert request["data"]["model"] == "enterprise-asr"
    assert request["files"]["file"][2] == "audio/mpeg"


def test_recognizer_sends_the_real_audio_content_type():
    with (
        patch.object(speech_recognizer, "ASR_API_URL", "https://asr.example.test"),
        patch.object(speech_recognizer.requests, "post", return_value=_Response()) as post,
    ):
        speech_recognizer.recognize_speech(b"\x1aE\xdf\xa3-audio", ".webm", "zh-CN")
    assert post.call_args.kwargs["files"]["file"][2] == "audio/webm"

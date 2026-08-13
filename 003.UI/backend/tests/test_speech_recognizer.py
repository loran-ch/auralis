from unittest.mock import patch

import pytest

from services import speech_recognizer


class _Response:
    ok = True
    status_code = 200

    def json(self):
        return {"text": "recognized sentence"}


class _BaiduResponse(_Response):
    def json(self):
        return {"err_no": 0, "err_msg": "success.", "result": ["Hello world"]}


class _BaiduNoSpeechResponse(_Response):
    def __init__(self, err_no):
        self.err_no = err_no

    def json(self):
        return {"err_no": self.err_no, "err_msg": "recognition error."}


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


def test_baidu_english_uses_english_model():
    with (
        patch.object(speech_recognizer, "ASR_API_URL", "https://vop.baidu.com/server_api"),
        patch.object(speech_recognizer, "_get_baidu_token", return_value="token"),
        patch.object(speech_recognizer.requests, "post", return_value=_BaiduResponse()) as post,
    ):
        result = speech_recognizer.recognize_speech(b"RIFFxxxxWAVEaudio", ".wav", "en")

    assert result == "Hello world"
    assert post.call_args.kwargs["json"]["dev_pid"] == 1737


def test_baidu_converts_iphone_m4a_before_recognition():
    wav = b"RIFFxxxxWAVEconverted"
    with (
        patch.object(speech_recognizer, "ASR_API_URL", "https://vop.baidu.com/server_api"),
        patch.object(speech_recognizer, "_get_baidu_token", return_value="token"),
        patch.object(speech_recognizer, "_convert_to_wav", return_value=wav) as convert,
        patch.object(speech_recognizer.requests, "post", return_value=_BaiduResponse()) as post,
    ):
        speech_recognizer.recognize_speech(b"m4a-audio", ".m4a", "zh-CN")

    convert.assert_called_once_with(b"m4a-audio", ".m4a")
    request = post.call_args.kwargs["json"]
    assert request["format"] == "wav"
    assert request["dev_pid"] == 1537
    assert request["len"] == len(wav)


def test_baidu_rejects_unsupported_source_language():
    with patch.object(speech_recognizer, "ASR_API_URL", "https://vop.baidu.com/server_api"):
        with pytest.raises(
            speech_recognizer.SpeechRecognitionUnavailable,
            match="暂不支持源语言 de",
        ):
            speech_recognizer.recognize_speech(b"RIFFxxxxWAVEaudio", ".wav", "de")


@pytest.mark.parametrize("err_no", [3301, 3307, 3314])
def test_baidu_silent_or_too_short_segment_is_not_service_unavailable(err_no):
    with (
        patch.object(speech_recognizer, "ASR_API_URL", "https://vop.baidu.com/server_api"),
        patch.object(speech_recognizer, "_get_baidu_token", return_value="token"),
        patch.object(
            speech_recognizer.requests,
            "post",
            return_value=_BaiduNoSpeechResponse(err_no),
        ),
    ):
        with pytest.raises(speech_recognizer.SpeechRecognitionNoSpeech):
            speech_recognizer.recognize_speech(
                b"RIFFxxxxWAVEsilent", ".wav", "en"
            )

import asyncio
from unittest.mock import patch

from routers import speech_stream
from services import realtime_speech, translator


def test_baidu_realtime_english_start_frame_uses_punctuated_model():
    frame = realtime_speech.baidu_start_frame(
        "en-US", "device-1", app_id="123456", app_key="api-key"
    )
    assert frame == {
        "type": "START",
        "data": {
            "appid": 123456,
            "appkey": "api-key",
            "dev_pid": 17372,
            "cuid": "device-1",
            "format": "pcm",
            "sample": 16000,
        },
    }


def test_realtime_no_speech_errors_do_not_trigger_service_fallback():
    assert realtime_speech.is_no_speech_error(-3005)
    assert realtime_speech.is_no_speech_error(3307)
    assert not realtime_speech.is_no_speech_error(-3004)


def test_context_translation_returns_only_current_line():
    with patch.object(
        translator,
        "translate_with_status",
        return_value={
            "text": (
                "我们讨论神经网络。\n"
                f"{translator._CONTEXT_CURRENT_MARKER}\n"
                "它根据误差调整权重。"
            ),
            "success": True,
            "provider": "fake",
            "warning": None,
        },
    ) as translate:
        result = translator.translate_with_context(
            "It adjusts the weights according to the error.",
            ["We discuss neural networks."],
            "en",
            "zh-CN",
        )

    assert result["text"] == "它根据误差调整权重。"
    assert result["context_applied"] is True
    assert "We discuss neural networks." in translate.call_args.args[0]
    assert translator._CONTEXT_CURRENT_MARKER in translate.call_args.args[0]


def test_context_translation_falls_back_when_provider_drops_line_boundaries():
    contextual = {
        "text": "上下文和当前句被合并了",
        "success": True,
        "provider": "fake",
        "warning": None,
    }
    current_only = {
        "text": "只翻译当前句",
        "success": True,
        "provider": "fake",
        "warning": None,
    }
    with patch.object(
        translator, "translate_with_status", side_effect=[contextual, current_only]
    ):
        result = translator.translate_with_context(
            "Current sentence.", ["Previous sentence."], "en", "zh-CN"
        )

    assert result["text"] == "只翻译当前句"
    assert result["context_applied"] is False


def test_stream_endpoint_falls_back_cleanly_when_realtime_is_not_configured():
    class FakeWebSocket:
        def __init__(self):
            self.messages = []
            self.close_code = None

        async def accept(self):
            return None

        async def receive_json(self):
            return {"type": "auth", "token": "test-token"}

        async def send_json(self, payload):
            self.messages.append(payload)

        async def close(self, code):
            self.close_code = code

    websocket = FakeWebSocket()

    with (
        patch.object(
            speech_stream,
            "_authenticate_stream",
            return_value=(7, "en", "zh-CN"),
        ),
        patch.object(speech_stream, "realtime_is_configured", return_value=False),
    ):
        asyncio.run(speech_stream.stream_lecture_audio(websocket, 12))

    message = websocket.messages[0]
    assert message["type"] == "unsupported"
    assert message["fallback"] is True
    assert websocket.close_code == 4403


def test_stream_endpoint_forwards_dynamic_and_final_results():
    class FakeWebSocket:
        def __init__(self):
            self.messages = []
            self.close_code = None

        async def accept(self):
            return None

        async def receive_json(self):
            return {"type": "auth", "token": "test-token", "offset_ms": 1200}

        async def receive(self):
            await asyncio.Event().wait()

        async def send_json(self, payload):
            self.messages.append(payload)

        async def close(self, code):
            self.close_code = code

    class FakeUpstream:
        def __init__(self):
            self.sent = []

        async def send(self, payload):
            self.sent.append(payload)

        def __aiter__(self):
            async def results():
                yield '{"type":"MID_TEXT","result":"Hello wor","sn":"a"}'
                yield (
                    '{"type":"FIN_TEXT","result":"Hello world.","sn":"a",'
                    '"start_time":100,"end_time":900}'
                )

            return results()

    class FakeConnection:
        def __init__(self, upstream):
            self.upstream = upstream

        async def __aenter__(self):
            return self.upstream

        async def __aexit__(self, *_args):
            return False

    websocket = FakeWebSocket()
    upstream = FakeUpstream()
    saved = {
        "id": 31,
        "source_text": "Hello world.",
        "translated_text": "你好，世界。",
    }
    translation = {
        "success": True,
        "provider": "fake",
        "warning": None,
        "context_applied": True,
    }

    with (
        patch.object(
            speech_stream,
            "_authenticate_stream",
            return_value=(7, "en", "zh-CN"),
        ),
        patch.object(speech_stream, "realtime_is_configured", return_value=True),
        patch.object(speech_stream, "_recent_source_sentences", return_value=[]),
        patch.object(
            speech_stream, "baidu_start_frame", return_value={"type": "START"}
        ),
        patch.object(
            speech_stream, "connect", return_value=FakeConnection(upstream)
        ),
        patch.object(
            speech_stream,
            "_translate_and_save",
            return_value=(saved, translation),
        ) as save,
    ):
        asyncio.run(speech_stream.stream_lecture_audio(websocket, 12))

    types = [message["type"] for message in websocket.messages]
    assert types == ["ready", "interim", "finalizing", "final", "closed"]
    assert websocket.messages[-2]["transcription"]["translated_text"] == "你好，世界。"
    assert save.call_args.args[-2:] == (1300, 2100)
    assert websocket.close_code == 1000

"""实时语音识别协议适配：百度 / 阿里云百炼（Fun-ASR）。"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from config import (
    ASR_ALIYUN_HEARTBEAT,
    ASR_ALIYUN_MAX_SENTENCE_SILENCE_MS,
    ASR_ALIYUN_MODEL,
    ASR_ALIYUN_REALTIME_URL,
    ASR_ALIYUN_SEMANTIC_PUNCTUATION,
    ASR_API_KEY,
    ASR_APP_ID,
    ASR_PROVIDER,
    DASHSCOPE_API_KEY,
)


_BAIDU_LANGUAGE_MODELS = {
    "zh": 15372,
    "zh-cn": 15372,
    "zh-tw": 15372,
    "en": 17372,
    "en-us": 17372,
    "en-gb": 17372,
}

# Fun-ASR / Paraformer language_hints 常用代码。
_ALIYUN_LANGUAGE_HINTS = {
    "zh": "zh",
    "zh-cn": "zh",
    "zh-tw": "zh",
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "ja": "ja",
    "ko": "ko",
    "yue": "yue",
    "de": "de",
    "fr": "fr",
    "ru": "ru",
}


def realtime_provider() -> str:
    return ASR_PROVIDER if ASR_PROVIDER in {"baidu", "aliyun"} else "baidu"


def baidu_realtime_model(language: str) -> int | None:
    return _BAIDU_LANGUAGE_MODELS.get((language or "").strip().lower())


def aliyun_language_hint(language: str) -> Optional[str]:
    return _ALIYUN_LANGUAGE_HINTS.get((language or "").strip().lower())


def realtime_is_configured(language: str) -> bool:
    provider = realtime_provider()
    if provider == "aliyun":
        return bool(DASHSCOPE_API_KEY and aliyun_language_hint(language))
    return bool(ASR_APP_ID and ASR_API_KEY and baidu_realtime_model(language))


# 兼容旧测试名
def realtime_model(language: str) -> int | None:
    return baidu_realtime_model(language)


def baidu_start_frame(
    language: str,
    cuid: str,
    app_id: str | None = None,
    app_key: str | None = None,
) -> dict:
    model = baidu_realtime_model(language)
    if model is None:
        raise ValueError(f"百度实时语音识别暂不支持源语言 {language or '未知'}")
    try:
        numeric_app_id = int(ASR_APP_ID if app_id is None else app_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("ASR_APP_ID 必须是百度语音应用的数字 App ID") from exc
    return {
        "type": "START",
        "data": {
            "appid": numeric_app_id,
            "appkey": ASR_API_KEY if app_key is None else app_key,
            "dev_pid": model,
            "cuid": cuid[:128] or uuid.uuid4().hex,
            "format": "pcm",
            "sample": 16000,
        },
    }


def baidu_stream_url(base_url: str) -> str:
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}sn={uuid.uuid4().hex}"


def is_no_speech_error(error_number: int) -> bool:
    # -3005 是实时接口的无效音频/噪音句；对应短语音接口的
    # 静音、音质过差及音频过短也一并视为正常空句。
    return error_number in {-3005, 3301, 3307, 3314}


def aliyun_stream_url(base_url: str | None = None) -> str:
    return (base_url or ASR_ALIYUN_REALTIME_URL).strip()


def aliyun_connect_headers(api_key: str | None = None) -> dict[str, str]:
    key = (api_key if api_key is not None else DASHSCOPE_API_KEY).strip()
    if not key:
        raise ValueError("DASHSCOPE_API_KEY 未配置")
    return {
        "Authorization": f"Bearer {key}",
        "user-agent": "LiveTrans/1.4",
    }


def aliyun_run_task_frame(
    language: str,
    task_id: str | None = None,
    model: str | None = None,
) -> dict:
    hint = aliyun_language_hint(language)
    if not hint:
        raise ValueError(f"阿里实时语音识别暂不支持源语言 {language or '未知'}")
    tid = (task_id or uuid.uuid4().hex).strip() or uuid.uuid4().hex
    return {
        "header": {
            "action": "run-task",
            "task_id": tid,
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "asr",
            "function": "recognition",
            "model": (model or ASR_ALIYUN_MODEL).strip() or "fun-asr-realtime",
            "parameters": {
                "format": "pcm",
                "sample_rate": 16000,
                # 课堂讲课：语义断句更完整；若要更低延迟可关掉并拉大静音阈值。
                "semantic_punctuation_enabled": bool(ASR_ALIYUN_SEMANTIC_PUNCTUATION),
                "max_sentence_silence": int(ASR_ALIYUN_MAX_SENTENCE_SILENCE_MS),
                # 配合持续静音 PCM，避免老师停顿太久被服务端空闲踢下线。
                "heartbeat": bool(ASR_ALIYUN_HEARTBEAT),
                "language_hints": [hint],
            },
            "input": {},
        },
    }


def aliyun_finish_task_frame(task_id: str) -> dict:
    return {
        "header": {
            "action": "finish-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {
            "input": {},
        },
    }


def parse_aliyun_event(raw: dict[str, Any]) -> dict[str, Any]:
    """把百炼事件归一成内部结构。

    返回字段：
    - kind: started | interim | final | finished | failed | heartbeat | ignore
    - text / utterance_id / start_offset_ms / end_offset_ms / message
    """
    header = raw.get("header") if isinstance(raw.get("header"), dict) else {}
    event = str(header.get("event") or "").strip().lower()
    task_id = str(header.get("task_id") or "").strip()
    error_code = header.get("error_code") or header.get("code")
    error_message = header.get("error_message") or header.get("message")

    if event in {"task-failed", "task_failed"} or error_code:
        return {
            "kind": "failed",
            "message": str(error_message or error_code or "阿里实时识别失败"),
            "utterance_id": task_id,
        }
    if event in {"task-started", "task_started"}:
        return {"kind": "started", "utterance_id": task_id}
    if event in {"task-finished", "task_finished"}:
        return {"kind": "finished", "utterance_id": task_id}

    if event not in {"result-generated", "result_generated"}:
        return {"kind": "ignore"}

    payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
    output = payload.get("output") if isinstance(payload.get("output"), dict) else {}
    sentence = output.get("sentence") if isinstance(output.get("sentence"), dict) else {}
    if sentence.get("heartbeat") is True:
        return {"kind": "heartbeat", "utterance_id": task_id}

    text = str(sentence.get("text") or "").strip()
    if not text:
        return {"kind": "ignore", "utterance_id": task_id}

    begin = sentence.get("begin_time", sentence.get("beginTime"))
    end = sentence.get("end_time", sentence.get("endTime"))
    try:
        start_ms = max(0, int(begin)) if begin is not None else 0
    except (TypeError, ValueError):
        start_ms = 0
    try:
        end_ms = max(0, int(end)) if end is not None else start_ms
    except (TypeError, ValueError):
        end_ms = start_ms

    sentence_end = bool(
        sentence.get("sentence_end")
        if "sentence_end" in sentence
        else sentence.get("sentenceEnd")
    )
    # 部分文档用 end_time 是否为空判断最终句。
    if not sentence_end and end is not None:
        sentence_end = True

    return {
        "kind": "final" if sentence_end else "interim",
        "text": text,
        "utterance_id": task_id or f"aliyun-{uuid.uuid4().hex[:12]}",
        "start_offset_ms": start_ms,
        "end_offset_ms": end_ms,
    }

"""百度实时语音识别协议适配。"""
import uuid

from config import ASR_APP_ID, ASR_API_KEY


_REALTIME_LANGUAGE_MODELS = {
    "zh": 15372,
    "zh-cn": 15372,
    "zh-tw": 15372,
    "en": 17372,
    "en-us": 17372,
    "en-gb": 17372,
}


def realtime_model(language: str) -> int | None:
    return _REALTIME_LANGUAGE_MODELS.get((language or "").strip().lower())


def realtime_is_configured(language: str) -> bool:
    return bool(ASR_APP_ID and ASR_API_KEY and realtime_model(language))


def baidu_start_frame(
    language: str,
    cuid: str,
    app_id: str | None = None,
    app_key: str | None = None,
) -> dict:
    model = realtime_model(language)
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

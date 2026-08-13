"""LiveTrans Voice — 英文→中文翻译服务（百度 / Google / MyMemory / 企业网关）"""
import hashlib
import html
import json
import logging
import random
import threading
import time

import requests

from config import (BAIDU_TRANSLATE_API_URL, BAIDU_TRANSLATE_APP_ID,
                    BAIDU_TRANSLATE_SECRET_KEY, ENTERPRISE_TRANSLATION_API_KEY,
                    ENTERPRISE_TRANSLATION_API_URL, GOOGLE_TRANSLATE_API_URL,
                    MYMEMORY_API_URL, TRANSLATION_CACHE_TTL_SECONDS,
                    TRANSLATION_PROVIDER_ORDER, TRANSLATION_TIMEOUT_SECONDS)


logger = logging.getLogger(__name__)
_cache: dict[tuple[str, str, str], tuple[float, str]] = {}
_cache_lock = threading.Lock()
_CACHE_MAX_ITEMS = 1000
_CONTEXT_CURRENT_MARKER = "[[[LTV_CONTEXT_CURRENT_7F31]]]"


def _get_cached(key: tuple[str, str, str]) -> str | None:
    with _cache_lock:
        cached = _cache.get(key)
        if not cached:
            return None
        expires_at, value = cached
        if expires_at <= time.monotonic():
            _cache.pop(key, None)
            return None
        return value


def _set_cached(key: tuple[str, str, str], value: str) -> None:
    if TRANSLATION_CACHE_TTL_SECONDS == 0:
        return
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX_ITEMS:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (time.monotonic() + TRANSLATION_CACHE_TTL_SECONDS, value)


# ─── 百度翻译 ────────────────────────────────────────────

def _translate_baidu(text: str, source: str, target: str) -> str:
    """百度通用文本翻译 API，国内可用，免费 100 万字符/月。"""
    salt = str(random.randint(32768, 65536))
    sign_str = BAIDU_TRANSLATE_APP_ID + text + salt + BAIDU_TRANSLATE_SECRET_KEY
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    params = {
        "q": text,
        "from": source.split("-")[0] if "-" in source else source,
        "to": target.split("-")[0] if "-" in target else target,
        "appid": BAIDU_TRANSLATE_APP_ID,
        "salt": salt,
        "sign": sign,
    }
    try:
        resp = requests.get(
            BAIDU_TRANSLATE_API_URL,
            params=params,
            headers={"User-Agent": "LiveTrans/1.4"},
            timeout=TRANSLATION_TIMEOUT_SECONDS,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("百度翻译请求失败: %s", exc)
        raise RuntimeError("百度翻译服务暂时不可用") from exc

    if not resp.ok or data.get("error_code"):
        err_msg = data.get("error_msg", f"HTTP {resp.status_code}")
        logger.warning("百度翻译返回错误: %s", err_msg)
        raise RuntimeError(f"百度翻译失败: {err_msg}")

    results = data.get("trans_result", [])
    return "".join(item.get("dst", "") for item in results if isinstance(item, dict)).strip()


# ─── Google 翻译 ─────────────────────────────────────────

def _translate_google(text: str, source: str, target: str) -> str:
    try:
        resp = requests.get(
            GOOGLE_TRANSLATE_API_URL,
            params={"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text},
            headers={"User-Agent": "LiveTrans/1.4"},
            timeout=TRANSLATION_TIMEOUT_SECONDS,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Google 翻译请求失败: %s", exc)
        raise RuntimeError("Google 翻译服务暂时不可用") from exc

    segments = data[0] if isinstance(data, list) and data else []
    return "".join(
        segment[0] for segment in segments
        if isinstance(segment, list) and segment and isinstance(segment[0], str)
    ).strip()


# ─── MyMemory 翻译 ───────────────────────────────────────

def _translate_mymemory(text: str, source: str, target: str) -> str:
    try:
        resp = requests.get(
            MYMEMORY_API_URL,
            params={"q": text, "langpair": f"{source}|{target}"},
            headers={"User-Agent": "LiveTrans/1.4"},
            timeout=TRANSLATION_TIMEOUT_SECONDS,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("MyMemory 翻译请求失败: %s", exc)
        raise RuntimeError("MyMemory 翻译服务暂时不可用") from exc

    if not isinstance(data, dict) or data.get("responseStatus") != 200:
        return ""
    return html.unescape(data.get("responseData", {}).get("translatedText", "")).strip()


# ─── 企业翻译网关 ────────────────────────────────────────

def _translate_enterprise(text: str, source: str, target: str) -> str:
    payload = json.dumps({"text": text, "source": source, "target": target}).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "LiveTrans/1.4",
    }
    if ENTERPRISE_TRANSLATION_API_KEY:
        headers["Authorization"] = f"Bearer {ENTERPRISE_TRANSLATION_API_KEY}"
    try:
        resp = requests.post(
            ENTERPRISE_TRANSLATION_API_URL,
            data=payload,
            headers=headers,
            timeout=TRANSLATION_TIMEOUT_SECONDS,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("企业翻译请求失败: %s", exc)
        raise RuntimeError("企业翻译服务暂时不可用") from exc

    if not isinstance(data, dict):
        return ""
    result = data.get("translated_text") or data.get("translation") or data.get("text")
    if isinstance(result, dict):
        result = result.get("text") or result.get("translated_text")
    return result.strip() if isinstance(result, str) else ""


# ─── 统一入口 ────────────────────────────────────────────

def translate_with_status(text: str, source: str = "en", target: str = "zh-CN") -> dict:
    """翻译并返回可观测状态；只有成功结果才进入短期缓存。"""
    normalized = text.strip()[:500]
    key = (normalized, source, target)
    cached = _get_cached(key)
    if cached is not None:
        return {"text": cached, "success": True, "provider": "cache", "warning": None}

    providers = {
        "baidu": _translate_baidu,
        "enterprise": _translate_enterprise,
        "google": _translate_google,
        "mymemory": _translate_mymemory,
    }
    for provider in TRANSLATION_PROVIDER_ORDER:
        try:
            result = providers[provider](normalized, source, target)
            if not result:
                logger.warning("%s 翻译服务返回空结果", provider)
                continue
            _set_cached(key, result)
            return {"text": result, "success": True, "provider": provider, "warning": None}
        except Exception as exc:
            logger.warning("%s 翻译服务不可用: %s", provider, exc)

    return {
        "text": normalized,
        "success": False,
        "provider": "fallback",
        "warning": "翻译服务暂时不可用，已保留原文",
    }


def translate_with_context(
    text: str,
    previous_sentences: list[str] | tuple[str, ...],
    source: str = "en",
    target: str = "zh-CN",
) -> dict:
    """使用最近几句作为翻译上下文，但只返回当前句的译文。

    通用机器翻译没有独立的 context 参数，因此翻译一个短滑动窗口，
    并用稳定标记分隔历史与当前句。服务商保留标记时只返回标记后的译文；
    若标记丢失，自动回退为仅翻译当前句，避免重复显示历史内容。
    """
    current = text.strip()[:500]
    # 上游根据 ASR_CONTEXT_SENTENCES 控制句数，这里只负责字符预算。
    context = [item.strip() for item in previous_sentences if item.strip()]
    if not current or not context:
        result = translate_with_status(current, source, target)
        return {**result, "context_applied": False}

    # 通用翻译入口最多处理 500 字符，必须优先完整保留当前句；
    # 从最近的上一句开始向前填充剩余预算。
    # 一个换行用于分隔标记与当前句；每条上下文再占一个换行。
    remaining = max(0, 500 - len(current) - len(_CONTEXT_CURRENT_MARKER) - 1)
    selected_context = []
    for sentence in reversed(context):
        if remaining <= 0:
            break
        clipped = sentence[-remaining:]
        selected_context.append(clipped)
        remaining -= len(clipped) + 1
    selected_context.reverse()
    block_lines = [*selected_context, _CONTEXT_CURRENT_MARKER, current]
    contextual = translate_with_status("\n".join(block_lines), source, target)
    translated_block = contextual["text"]
    if contextual["success"] and _CONTEXT_CURRENT_MARKER in translated_block:
        current_translation = translated_block.rsplit(
            _CONTEXT_CURRENT_MARKER, 1
        )[-1].strip()
    else:
        current_translation = ""
    if current_translation:
        return {
            **contextual,
            "text": current_translation,
            "context_applied": True,
        }

    result = translate_with_status(current, source, target)
    return {**result, "context_applied": False}


def translate(text: str, source: str = "en", target: str = "zh-CN") -> str:
    """兼容课堂演示调用；失败时保留原文。"""
    return translate_with_status(text, source, target)["text"]

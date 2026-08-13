"""可替换的服务端语音识别客户端（支持百度 / 通用 multipart）。"""
import base64
import json
import logging
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import requests

from config import (
    ASR_API_KEY, ASR_API_SECRET, ASR_API_URL, ASR_MODEL, ASR_TIMEOUT_SECONDS,
)


logger = logging.getLogger(__name__)

_AUDIO_CONTENT_TYPES = {
    ".mp3": "audio/mpeg",
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}

_BAIDU_NATIVE_FORMATS = {".pcm", ".wav", ".amr"}
_BAIDU_LANGUAGE_MODELS = {
    "zh": 1537,
    "zh-cn": 1537,
    "zh-tw": 1537,
    "en": 1737,
    "en-us": 1737,
    "en-gb": 1737,
}


class SpeechRecognitionUnavailable(RuntimeError):
    """ASR 未配置或上游暂时不可用。"""


def _is_baidu(url: str) -> bool:
    return "baidu.com" in url or "vop.baidu" in url


# ─── 百度 OAuth Access Token ───────────────────────────

_baidu_token: str | None = None
_baidu_token_expiry: float = 0.0
_BAIDU_OAUTH_URL = "https://aip.baidubce.com/oauth/2.0/token"


def _get_baidu_token() -> str:
    """获取或刷新百度 OAuth Access Token（缓存至过期前 1 小时）。"""
    global _baidu_token, _baidu_token_expiry
    now = time.time()
    if _baidu_token and now < _baidu_token_expiry - 3600:
        return _baidu_token
    if not ASR_API_SECRET:
        raise SpeechRecognitionUnavailable(
            "百度语音识别需要 API Key + Secret Key。"
            "请在百度 AI 控制台获取 Secret Key 并填入 .env 的 ASR_API_SECRET"
        )
    try:
        resp = requests.post(
            _BAIDU_OAUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": ASR_API_KEY,
                "client_secret": ASR_API_SECRET,
            },
            timeout=10,
        )
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("百度 OAuth token 获取失败: %s", exc)
        raise SpeechRecognitionUnavailable(
            "百度语音识别认证失败，请检查 API Key 和 Secret Key"
        ) from exc
    token = data.get("access_token")
    if not token:
        err = data.get("error_description") or data.get("error") or "未知错误"
        logger.warning("百度 OAuth 返回错误: %s", err)
        raise SpeechRecognitionUnavailable(f"百度语音识别认证失败: {err}")
    _baidu_token = token
    _baidu_token_expiry = now + data.get("expires_in", 2592000)
    logger.info("百度 OAuth token 已刷新，有效期 %s 秒", data.get("expires_in"))
    return _baidu_token


# ─── 音频格式转换（ffmpeg）───────────────────────────

def _find_ffmpeg() -> str:
    """查找 ffmpeg 可执行文件（Windows winget 安装不在默认 PATH 中）。"""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5, check=True)
        return "ffmpeg"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    try:
        packages = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
        for pkg in packages.glob("Gyan.FFmpeg_*"):
            for exe in pkg.glob("ffmpeg-*-full_build/bin/ffmpeg.exe"):
                return str(exe)
    except Exception:
        pass
    raise SpeechRecognitionUnavailable(
        "需要安装 ffmpeg 才能使用百度语音识别。请运行: winget install ffmpeg"
    )


def _convert_to_wav(contents: bytes, source_ext: str) -> bytes:
    """将任意音频转为 16kHz 单声道 PCM WAV，供百度 ASR 使用。"""
    ext = source_ext.lower().lstrip(".")
    ffmpeg = _find_ffmpeg()
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / f"input.{ext}"
        dst = Path(tmpdir) / "output.wav"
        src.write_bytes(contents)
        try:
            subprocess.run(
                [ffmpeg, "-y", "-i", str(src),
                 "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000",
                 "-f", "wav", str(dst)],
                capture_output=True,
                timeout=30,
                check=True,
            )
        except FileNotFoundError:
            raise SpeechRecognitionUnavailable(
                "需要安装 ffmpeg 才能使用百度语音识别。请运行: winget install ffmpeg"
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace")[:300]
            logger.warning("ffmpeg 转换失败: %s", stderr)
            raise SpeechRecognitionUnavailable("音频格式转换失败，请检查 ffmpeg 是否正确安装")
        return dst.read_bytes()


# ─── 百度语音识别 ──────────────────────────────────────

def _recognize_baidu(contents: bytes, extension: str, language: str) -> str:
    ext = extension.lower()
    language_code = (language or "zh-CN").strip().lower()
    dev_pid = _BAIDU_LANGUAGE_MODELS.get(language_code)
    if dev_pid is None:
        raise SpeechRecognitionUnavailable(
            f"百度短语音识别暂不支持源语言 {language or '未知'}，请切换中文或英语"
        )

    if ext not in _BAIDU_NATIVE_FORMATS:
        logger.info("百度 ASR 不支持 %s 格式，尝试用 ffmpeg 转换为 wav", ext)
        contents = _convert_to_wav(contents, ext)
        ext = ".wav"

    baidu_format = {"pcm": "pcm", "wav": "wav", "amr": "amr", "m4a": "m4a"}[ext.lstrip(".")]

    body = {
        "format": baidu_format,
        "rate": 16000,
        "channel": 1,
        "cuid": uuid.uuid4().hex[:16],
        "token": _get_baidu_token(),
        "dev_pid": dev_pid,
        "speech": base64.b64encode(contents).decode("ascii"),
        "len": len(contents),
    }
    logger.info(
        "百度 ASR 请求: format=%s language=%s dev_pid=%d size=%d",
        baidu_format,
        language_code,
        dev_pid,
        len(contents),
    )
    try:
        resp = requests.post(
            ASR_API_URL,
            json=body,
            headers={"Accept": "application/json", "User-Agent": "LiveTrans/1.4"},
            timeout=ASR_TIMEOUT_SECONDS,
        )
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("百度 ASR 调用失败: %s", exc)
        raise SpeechRecognitionUnavailable("百度语音识别服务暂时不可用") from exc

    if not resp.ok:
        logger.warning("百度 ASR 返回 HTTP %s", resp.status_code)
        raise SpeechRecognitionUnavailable(
            f"百度语音识别返回错误（HTTP {resp.status_code}）"
        )

    err_no = data.get("err_no", -1)
    if err_no != 0:
        err_msg = data.get("err_msg", "未知错误")
        logger.warning("百度 ASR 识别失败: err_no=%s err_msg=%s", err_no, err_msg)
        raise SpeechRecognitionUnavailable(f"百度语音识别失败: {err_msg}")

    result = data.get("result", [])
    text = "".join(result) if isinstance(result, list) else str(result)
    text = text.strip()
    if not text:
        raise SpeechRecognitionUnavailable("百度语音识别未返回文本")
    return text[:4000]


# ─── 通用 multipart ASR ────────────────────────────────

def _recognize_generic(contents: bytes, extension: str, language: str) -> str:
    content_type = _AUDIO_CONTENT_TYPES.get(extension.lower())
    if not content_type:
        raise SpeechRecognitionUnavailable("语音识别不支持该音频格式")

    files = {"file": (f"segment{extension}", contents, content_type)}
    data = {}
    if ASR_MODEL:
        data["model"] = ASR_MODEL
    if language:
        data["language"] = language.split("-", 1)[0]

    headers = {"Accept": "application/json", "User-Agent": "LiveTrans/1.4"}
    if ASR_API_KEY:
        headers["Authorization"] = f"Bearer {ASR_API_KEY}"

    try:
        resp = requests.post(
            ASR_API_URL,
            files=files,
            data=data,
            headers=headers,
            timeout=ASR_TIMEOUT_SECONDS,
        )
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("ASR 服务调用失败: %s", exc)
        raise SpeechRecognitionUnavailable("语音识别服务暂时不可用") from exc

    if not resp.ok:
        logger.warning("ASR 服务返回 HTTP %s", resp.status_code)
        raise SpeechRecognitionUnavailable(
            f"语音识别服务返回错误（HTTP {resp.status_code}）"
        )

    text = data.get("text") or data.get("transcript") or data.get("result")
    if isinstance(text, dict):
        text = text.get("text")
    text = text.strip() if isinstance(text, str) else ""
    if not text:
        raise SpeechRecognitionUnavailable("语音识别未返回文本")
    return text[:4000]


# ─── 统一入口 ──────────────────────────────────────────

def recognize_speech(contents: bytes, extension: str, language: str) -> str:
    """把短音频发送到 ASR 服务并返回文本（自动适配百度/通用格式）。"""
    if not ASR_API_URL:
        raise SpeechRecognitionUnavailable("未配置语音识别服务")

    if _is_baidu(ASR_API_URL):
        return _recognize_baidu(contents, extension, language)
    return _recognize_generic(contents, extension, language)

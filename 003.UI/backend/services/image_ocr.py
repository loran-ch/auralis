"""通用图片 OCR：助手截图提问与课堂帧共用轻量 Tesseract 流程。"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps
import pytesseract

from config import OCR_LANGUAGES, TESSDATA_DIR, TESSERACT_CMD


_MAX_OCR_CHARS = 2000


def resolve_tesseract() -> str:
    if TESSERACT_CMD and shutil.which(TESSERACT_CMD):
        return TESSERACT_CMD
    configured = Path(TESSERACT_CMD)
    if configured.is_file():
        return str(configured)
    windows_default = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
    if windows_default.is_file():
        return str(windows_default)
    raise RuntimeError("Tesseract OCR 未安装或未配置")


def ocr_image_path(path: Path, *, max_chars: int = _MAX_OCR_CHARS) -> dict:
    """对本地图片做 OCR。失败不抛致命错，返回 status=failed/empty。"""
    if not path.is_file():
        return {
            "ocr_status": "failed",
            "ocr_text": "",
            "ocr_confidence": 0.0,
            "error_message": "图片文件不存在",
        }
    try:
        pytesseract.pytesseract.tesseract_cmd = resolve_tesseract()
        os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR
        with Image.open(path) as image:
            processed = ImageOps.autocontrast(ImageOps.grayscale(image))
            data = pytesseract.image_to_data(
                processed,
                lang=OCR_LANGUAGES,
                config="--psm 6",
                output_type=pytesseract.Output.DICT,
            )
    except Exception as exc:
        return {
            "ocr_status": "failed",
            "ocr_text": "",
            "ocr_confidence": 0.0,
            "error_message": str(exc)[:200],
        }

    words, confidences = [], []
    for word, confidence in zip(data.get("text", []), data.get("conf", [])):
        word = str(word or "").strip()
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = -1
        if word and confidence >= 0:
            words.append(word)
            confidences.append(confidence)
    text = " ".join(words).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    if not text:
        return {
            "ocr_status": "empty",
            "ocr_text": "",
            "ocr_confidence": 0.0,
            "error_message": "未识别到文字，可改用更清晰截图或补充文字说明",
        }
    return {
        "ocr_status": "ready",
        "ocr_text": text,
        "ocr_confidence": round(sum(confidences) / len(confidences), 1) if confidences else 0.0,
        "error_message": None,
    }


def detect_image_extension(header: bytes, content_type: Optional[str] = None) -> Optional[str]:
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp"
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    return mapping.get((content_type or "").lower())

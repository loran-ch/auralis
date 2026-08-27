"""学习助手截图：保存、校验与拼装提问上下文。"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional


ASSISTANT_UPLOAD_DIR = (
    Path(__file__).resolve().parent.parent.parent / "frontend" / "uploads" / "assistant"
)
ASSISTANT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_IMAGE_QUESTION = "请根据截图帮我看看这是什么问题或错误，并结合课堂笔记解释。"


def build_image_url(user_id: int, filename: str) -> str:
    return f"/uploads/assistant/{filename}"


def is_owned_assistant_image(url: Optional[str], user_id: int) -> bool:
    if not url or not url.startswith("/uploads/assistant/"):
        return False
    name = Path(url).name
    return name.startswith(f"{int(user_id)}_")


def local_path_for_url(url: str) -> Path:
    name = Path(url).name
    return (ASSISTANT_UPLOAD_DIR / name).resolve()


def compose_question_with_screenshot(question: Optional[str], image_ocr: Optional[str]) -> tuple[str, str]:
    """返回 (展示给用户的问题, 送给模型/检索的问题)。"""
    display = (question or "").strip() or DEFAULT_IMAGE_QUESTION
    ocr = (image_ocr or "").strip()
    if not ocr:
        return display, display
    enriched = (
        f"{display}\n\n【截图文字识别】\n{ocr[:1500]}\n"
        "请结合课堂笔记解释截图中的问题/错误；若课堂未覆盖，用【补充说明】标注。"
    )
    return display, enriched

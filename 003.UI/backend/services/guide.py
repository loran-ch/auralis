"""前台功能说明：公开读取，管理员编辑。"""
from __future__ import annotations

import logging
import re
import threading
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from database import engine
from models.guide import AppGuide
from models.user import User
from services.admin import write_audit_log


logger = logging.getLogger(__name__)

RECORDER_FEATURES_SLUG = "recorder_features"
_ICON_RE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_TABLE_READY = False
_TABLE_LOCK = threading.Lock()

DEFAULT_GUIDES: dict[str, dict[str, Any]] = {
    RECORDER_FEATURES_SLUG: {
        "slug": RECORDER_FEATURES_SLUG,
        "title": "课堂学习助手",
        "subtitle": "从上课录音到课后复习提问，一条完整学习链路：听懂、记下、汇总、带走、再提问。",
        "footer_hint": "建议先在「课程中心」建课 → 回来点绿色麦克风开始 · 未登录会提示注册",
        "items": [
            {
                "icon": "school",
                "title": "课前：课程中心建课",
                "body": "创建课程并设置授课/翻译语言；录音前选好课程，课后记录会自动归档，方便按学期管理。",
            },
            {
                "icon": "subtitles",
                "title": "课上：实时双语字幕",
                "body": "麦克风录音后，原文与译文同步滚动。也可关闭翻译，只保留录音与文字，适合母语课堂。",
            },
            {
                "icon": "star",
                "title": "课上：一键收藏重点",
                "body": "听到关键句点星标，标成重要 / 疑问 / 考点 / 定义；课后在「知识卡片」里集中复习。",
            },
            {
                "icon": "description",
                "title": "课后：自动课堂简报",
                "body": "结束录音后生成概览、重点、术语与待确认作业；每条结论可跳回字幕时间点核对。",
            },
            {
                "icon": "folder_zip",
                "title": "资料：上传与一键导出",
                "body": "在课堂记录里上传 PPT / PDF / 图片；可导出简报 Markdown，或打包下载全部学习资料。",
            },
            {
                "icon": "psychology",
                "title": "随时：学习助手问答",
                "body": "按课程检索笔记、拆解作业，也可粘贴报错/题目截图提问；回答会附上可跳转的课堂证据。",
            },
        ],
    }
}


def ensure_guide_table() -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return
    with _TABLE_LOCK:
        if _TABLE_READY:
            return
        AppGuide.__table__.create(bind=engine, checkfirst=True)
        _TABLE_READY = True


def _clip(text: str, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def sanitize_icon(icon: str) -> str:
    value = (icon or "").strip().lower()
    if _ICON_RE.match(value):
        return value
    return "info"


def sanitize_items(items: Any) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    if not isinstance(items, list):
        return cleaned
    for raw in items[:20]:
        if not isinstance(raw, dict):
            continue
        title = _clip(str(raw.get("title") or ""), 64)
        body = _clip(str(raw.get("body") or ""), 300)
        if not title or not body:
            continue
        cleaned.append({
            "icon": sanitize_icon(str(raw.get("icon") or "info")),
            "title": title,
            "body": body,
        })
        if len(cleaned) >= 8:
            break
    return cleaned


def default_guide(slug: str) -> dict[str, Any]:
    data = DEFAULT_GUIDES.get(slug) or DEFAULT_GUIDES[RECORDER_FEATURES_SLUG]
    return {
        "slug": slug if slug in DEFAULT_GUIDES else RECORDER_FEATURES_SLUG,
        "title": data["title"],
        "subtitle": data.get("subtitle") or "",
        "items": list(data.get("items") or []),
        "footer_hint": data.get("footer_hint") or "",
        "updated_at": None,
        "updated_by": None,
    }


def to_public_dict(row: AppGuide) -> dict[str, Any]:
    items = sanitize_items(row.items)
    if not items:
        items = list(default_guide(row.slug)["items"])
    return {
        "slug": row.slug,
        "title": row.title or default_guide(row.slug)["title"],
        "subtitle": row.subtitle or "",
        "items": items,
        "footer_hint": row.footer_hint or "",
        "updated_at": row.updated_at,
        "updated_by": row.updated_by_name,
    }


def _looks_like_legacy_recorder_guide(row: AppGuide) -> bool:
    """识别尚未人工定制过的旧版内置说明，便于一次性迁到最新默认文案。"""
    if (row.title or "").strip() == "课堂实时翻译助手":
        return True
    items = row.items if isinstance(row.items, list) else []
    titles = {(item.get("title") or "").strip() for item in items if isinstance(item, dict)}
    legacy_five = {"实时双语字幕", "多语种听译", "一键收藏知识点", "课堂回看", "课后课堂助教"}
    legacy_three = {"课上：实时双语字幕", "课后：简报与学习资料", "随时：学习助手问答"}
    if len(items) == 5 and legacy_five.issubset(titles):
        return True
    if len(items) == 3 and legacy_three.issubset(titles):
        return True
    return False


def _seed_if_missing(db: Session, slug: str) -> AppGuide:
    row = db.query(AppGuide).filter(AppGuide.slug == slug).first()
    data = default_guide(slug)
    if row:
        if slug == RECORDER_FEATURES_SLUG and _looks_like_legacy_recorder_guide(row):
            row.title = data["title"]
            row.subtitle = data["subtitle"]
            row.items = data["items"]
            row.footer_hint = data["footer_hint"]
            row.updated_at = datetime.now()
            db.commit()
            db.refresh(row)
        return row
    row = AppGuide(
        slug=data["slug"],
        title=data["title"],
        subtitle=data["subtitle"],
        items=data["items"],
        footer_hint=data["footer_hint"],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_guide(db: Session, slug: str = RECORDER_FEATURES_SLUG) -> dict[str, Any]:
    slug = (slug or RECORDER_FEATURES_SLUG).strip() or RECORDER_FEATURES_SLUG
    if slug not in DEFAULT_GUIDES:
        slug = RECORDER_FEATURES_SLUG
    try:
        ensure_guide_table()
        row = _seed_if_missing(db, slug)
        return to_public_dict(row)
    except Exception:
        logger.exception("读取功能说明失败，使用内置默认文案")
        db.rollback()
        return default_guide(slug)


def update_guide(
    db: Session,
    slug: str,
    payload: dict[str, Any],
    admin: User,
    ip_address: Optional[str] = None,
) -> dict[str, Any]:
    slug = (slug or RECORDER_FEATURES_SLUG).strip() or RECORDER_FEATURES_SLUG
    if slug not in DEFAULT_GUIDES:
        raise ValueError("不支持的说明标识")
    items = sanitize_items(payload.get("items"))
    if not items:
        raise ValueError("至少需要一条说明")
    ensure_guide_table()
    row = _seed_if_missing(db, slug)
    row.title = _clip(str(payload.get("title") or ""), 128) or default_guide(slug)["title"]
    row.subtitle = _clip(str(payload.get("subtitle") or ""), 512)
    row.footer_hint = _clip(str(payload.get("footer_hint") or ""), 256)
    row.items = items
    row.updated_by_name = admin.nickname or admin.username
    row.updated_at = datetime.now()
    write_audit_log(
        db,
        admin,
        action="guide.update",
        target_type="guide",
        target_id=row.id,
        detail={"slug": slug, "title": row.title, "item_count": len(items)},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(row)
    logger.info("管理员 %s 更新了功能说明 %s", row.updated_by_name, slug)
    return to_public_dict(row)

"""课堂视频后处理：抽帧 OCR、二次核验与确认后的短片导出。"""
from __future__ import annotations

import re
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from PIL import Image, ImageOps
import pytesseract
from sqlalchemy.orm import Session

from config import FFMPEG_BINARY, OCR_LANGUAGES, TESSDATA_DIR, TESSERACT_CMD
from models.lecture import (MediaAsset, MediaClipCandidate, Transcription,
                            TranscriptionVerification)
from services.speech_recognizer import (SpeechRecognitionNoSpeech,
                                        SpeechRecognitionUnavailable,
                                        recognize_speech)


_EMPHASIS_RE = re.compile(r"(重点|重要|考试|考点|作业|记住|注意|总结|homework|exam|important|remember)", re.I)
_MEDIA_ROOT = Path(__file__).resolve().parent.parent.parent / "frontend" / "uploads" / "media"
_AUDIO_ROOT = Path(__file__).resolve().parent.parent.parent / "frontend" / "uploads" / "audio"
_FRAME_DIR = _MEDIA_ROOT / "frames"
_CLIP_DIR = _MEDIA_ROOT / "clips"
_FRAME_DIR.mkdir(parents=True, exist_ok=True)
_CLIP_DIR.mkdir(parents=True, exist_ok=True)


def _url_path(url: str) -> Path:
    relative = Path(url or "").relative_to("/uploads/media")
    path = (_MEDIA_ROOT / relative).resolve()
    if _MEDIA_ROOT.resolve() not in path.parents:
        raise ValueError("媒体路径无效")
    return path


def _audio_path(url: str) -> Path:
    relative = Path(url or "").relative_to("/uploads/audio")
    path = (_AUDIO_ROOT / relative).resolve()
    if _AUDIO_ROOT.resolve() not in path.parents:
        raise ValueError("音频路径无效")
    return path


def _ffmpeg() -> str:
    if FFMPEG_BINARY and shutil.which(FFMPEG_BINARY):
        return FFMPEG_BINARY
    configured = Path(FFMPEG_BINARY)
    if configured.is_file():
        return str(configured)
    project_binary = Path(__file__).resolve().parent.parent / "tools" / "ffmpeg" / "ffmpeg.exe"
    if project_binary.is_file():
        return str(project_binary)
    winget_root = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    for package in winget_root.glob("Gyan.FFmpeg_*"):
        found = list(package.glob("ffmpeg-*-full_build/bin/ffmpeg.exe"))
        if found:
            return str(found[0])
    raise RuntimeError("FFmpeg 未安装或未配置")


def _tesseract() -> str:
    if TESSERACT_CMD and shutil.which(TESSERACT_CMD):
        return TESSERACT_CMD
    configured = Path(TESSERACT_CMD)
    if configured.is_file():
        return str(configured)
    windows_default = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
    if windows_default.is_file():
        return str(windows_default)
    raise RuntimeError("Tesseract OCR 未安装或未配置")


def _ocr_frame(asset: MediaAsset) -> None:
    path = _url_path(asset.url)
    if not path.is_file():
        raise RuntimeError("关键帧文件不存在")
    pytesseract.pytesseract.tesseract_cmd = _tesseract()
    # Windows 的命令行参数在目录包含空格时可能给语言模型路径附加引号；
    # 使用 Tesseract 原生环境变量避免这一解析差异。
    os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR
    with Image.open(path) as image:
        # 轻量预处理足以改善投影屏幕/白板对比度，保留原图作为可追溯证据。
        processed = ImageOps.autocontrast(ImageOps.grayscale(image))
        config = "--psm 6"
        data = pytesseract.image_to_data(
            processed, lang=OCR_LANGUAGES, config=config, output_type=pytesseract.Output.DICT,
        )
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
    metadata = dict(asset.metadata_json or {})
    metadata.update({
        "ocr_status": "ready",
        "ocr_text": " ".join(words)[:4000],
        "ocr_confidence": round(sum(confidences) / len(confidences), 1) if confidences else 0,
        "ocr_language": OCR_LANGUAGES,
    })
    asset.metadata_json = metadata
    asset.status = "ready"
    asset.error_message = None


def _extract_frames(db: Session, video: MediaAsset) -> list[MediaAsset]:
    existing = db.query(MediaAsset).filter(
        MediaAsset.lecture_id == video.lecture_id, MediaAsset.media_type == "frame",
    ).count()
    if existing:
        return []
    source = _url_path(video.url)
    if not source.is_file():
        raise RuntimeError("课堂视频文件不存在")
    prefix = f"{video.user_id}_{video.lecture_id}_{uuid.uuid4().hex[:8]}"
    pattern = _FRAME_DIR / f"{prefix}_%03d.jpg"
    subprocess.run([
        _ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vf", "fps=1/15,scale='min(1280,iw)':-2", "-frames:v", "120", str(pattern),
    ], timeout=600, check=True, capture_output=True)
    result = []
    for index, path in enumerate(sorted(_FRAME_DIR.glob(f"{prefix}_*.jpg")), start=1):
        asset = MediaAsset(
            lecture_id=video.lecture_id, user_id=video.user_id, media_type="frame", status="processing",
            url=f"/uploads/media/frames/{path.name}", content_type="image/jpeg", size_bytes=path.stat().st_size,
            start_offset_ms=(index - 1) * 15_000, metadata_json={"ocr_status": "processing", "source": "ffmpeg"},
        )
        db.add(asset)
        result.append(asset)
    db.flush()
    return result


def process_lecture_media(db: Session, lecture_id: int, user_id: int) -> dict:
    """课后后台任务；失败只记录媒体状态，绝不影响课堂原文与简报。"""
    video = db.query(MediaAsset).filter(
        MediaAsset.lecture_id == lecture_id, MediaAsset.user_id == user_id,
        MediaAsset.media_type == "video",
    ).order_by(MediaAsset.id.desc()).first()
    extracted = 0
    if video:
        try:
            extracted = len(_extract_frames(db, video))
        except Exception as exc:
            video.status = "unavailable"
            video.error_message = str(exc)[:512]
            db.commit()
    frames = db.query(MediaAsset).filter(
        MediaAsset.lecture_id == lecture_id, MediaAsset.user_id == user_id,
        MediaAsset.media_type == "frame",
    ).all()
    processed = 0
    for frame in frames:
        if (frame.metadata_json or {}).get("ocr_status") == "ready":
            continue
        try:
            _ocr_frame(frame)
            processed += 1
        except Exception as exc:
            metadata = dict(frame.metadata_json or {})
            metadata["ocr_status"] = "failed"
            frame.metadata_json = metadata
            frame.status = "failed"
            frame.error_message = str(exc)[:512]
    db.commit()
    return {"extracted": extracted, "ocr_processed": processed}


def generate_clip_candidates(db: Session, lecture_id: int, user_id: int) -> int:
    """根据收藏和强调语句生成候选时间轴；实际导出需用户明确触发。"""
    db.query(MediaClipCandidate).filter(
        MediaClipCandidate.lecture_id == lecture_id, MediaClipCandidate.user_id == user_id,
        MediaClipCandidate.status == "candidate",
    ).delete(synchronize_session=False)
    rows = db.query(Transcription).filter(
        Transcription.lecture_id == lecture_id, Transcription.user_id == user_id,
    ).order_by(Transcription.sentence_order).all()
    created, last_end = 0, -1
    for row in rows:
        text = f"{row.source_text or ''} {row.translated_text or ''}"
        score = (3 if row.is_bookmarked else 0) + (3 if _EMPHASIS_RE.search(text) else 0)
        if score < 3:
            continue
        center = int(row.start_offset_ms or 0)
        start, end = max(0, center - 15_000), max(center + 20_000, int(row.end_offset_ms or center) + 25_000)
        if start < last_end + 8_000:
            continue
        db.add(MediaClipCandidate(
            lecture_id=lecture_id, user_id=user_id,
            title="已收藏的课堂片段" if row.is_bookmarked else "老师强调的内容",
            reason=(row.translated_text or row.source_text or "")[:480],
            start_offset_ms=start, end_offset_ms=end, score=float(score),
        ))
        last_end, created = end, created + 1
        if created >= 12:
            break
    db.commit()
    return created


def export_clip(db: Session, candidate: MediaClipCandidate) -> None:
    video = db.query(MediaAsset).filter(
        MediaAsset.lecture_id == candidate.lecture_id, MediaAsset.user_id == candidate.user_id,
        MediaAsset.media_type == "video",
    ).order_by(MediaAsset.id.desc()).first()
    if not video:
        candidate.status, candidate.error_message = "unavailable", "该课堂没有可导出的视频"
        db.commit()
        return
    try:
        source = _url_path(video.url)
        name = f"clip_{candidate.user_id}_{candidate.id}_{uuid.uuid4().hex[:8]}.mp4"
        target = (_CLIP_DIR / name).resolve()
        duration = max(1, (candidate.end_offset_ms - candidate.start_offset_ms) / 1000)
        subprocess.run([
            _ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(candidate.start_offset_ms / 1000), "-i", str(source), "-t", str(duration),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac",
            "-movflags", "+faststart", str(target),
        ], timeout=900, check=True, capture_output=True)
        candidate.media_url, candidate.status = f"/uploads/media/clips/{name}", "ready"
        candidate.error_message = None
    except Exception as exc:
        candidate.status, candidate.error_message = "failed", str(exc)[:512]
    db.commit()


def verify_transcription(db: Session, verification: TranscriptionVerification, lecture, transcription) -> None:
    """提取对应音频重识别，并带回同时间段 OCR 证据；原句始终保留。"""
    start = max(0, int(transcription.start_offset_ms or 0) - 3000)
    end = max(start + 5000, int(transcription.end_offset_ms or start + 1000) + 4000)
    frames = db.query(MediaAsset).filter(
        MediaAsset.lecture_id == lecture.id, MediaAsset.user_id == lecture.user_id,
        MediaAsset.media_type == "frame", MediaAsset.start_offset_ms >= start - 5000,
        MediaAsset.start_offset_ms <= end + 5000,
    ).all()
    ocr_evidence = [{"offset_ms": frame.start_offset_ms, "text": (frame.metadata_json or {}).get("ocr_text", ""),
                     "confidence": (frame.metadata_json or {}).get("ocr_confidence", 0)} for frame in frames]
    video = db.query(MediaAsset).filter(
        MediaAsset.lecture_id == lecture.id, MediaAsset.user_id == lecture.user_id,
        MediaAsset.media_type == "video",
    ).order_by(MediaAsset.id.desc()).first()
    try:
        source_path = _url_path(video.url) if video else _audio_path(getattr(lecture, "audio_url", ""))
    except ValueError:
        source_path = None
    if not source_path or not source_path.is_file():
        verification.status, verification.error_message = "unavailable", "该课堂没有可核验的音频或视频"
        verification.evidence_json = {"ocr": ocr_evidence, "range_ms": [start, end]}
        db.commit()
        return
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_file = Path(temp_dir) / "verification.wav"
            subprocess.run([
                _ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-ss", str(start / 1000),
                "-i", str(source_path), "-t", str((end - start) / 1000),
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio_file),
            ], timeout=90, check=True, capture_output=True)
            secondary = recognize_speech(audio_file.read_bytes(), ".wav", lecture.source_lang)
        verification.secondary_asr = secondary
        verification.evidence_json = {"ocr": ocr_evidence, "range_ms": [start, end]}
        if re.sub(r"\W", "", secondary).lower() != re.sub(r"\W", "", transcription.source_text or "").lower():
            verification.status, verification.suggested_text = "suggested", secondary
        else:
            verification.status = "unchanged"
    except (SpeechRecognitionUnavailable, SpeechRecognitionNoSpeech) as exc:
        verification.status, verification.error_message = "unavailable", str(exc)[:512]
        verification.evidence_json = {"ocr": ocr_evidence, "range_ms": [start, end]}
    except Exception as exc:
        verification.status, verification.error_message = "failed", str(exc)[:512]
    db.commit()

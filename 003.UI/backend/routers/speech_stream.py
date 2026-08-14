"""课堂实时语音识别 WebSocket。"""
import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from config import (ASR_CONTEXT_SENTENCES, ASR_REALTIME_PREVIEW_INTERVAL_MS,
                    ASR_REALTIME_URL)
from database import SessionLocal
from models.lecture import Lecture, Transcription
from services.auth import authenticate_access_token
from services.lecture import get_recent_source_sentences, transcribe_audio
from services.realtime_speech import (baidu_start_frame, baidu_stream_url,
                                      is_no_speech_error,
                                      realtime_is_configured)
from services.translator import translate_with_context


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/lectures", tags=["实时语音识别"])


def _authenticate_stream(token: str, lecture_id: int) -> tuple[int, str, str] | None:
    db = SessionLocal()
    try:
        user = authenticate_access_token(db, token)
        if not user:
            return None
        lecture = db.query(Lecture).filter(
            Lecture.id == lecture_id,
            Lecture.user_id == user.id,
            Lecture.status == "recording",
        ).first()
        if not lecture:
            return None
        return user.id, lecture.source_lang, lecture.target_lang
    finally:
        db.close()


def _recent_source_sentences(lecture_id: int, user_id: int) -> list[str]:
    if ASR_CONTEXT_SENTENCES == 0:
        return []
    db = SessionLocal()
    try:
        return get_recent_source_sentences(db, lecture_id, user_id, ASR_CONTEXT_SENTENCES)
    finally:
        db.close()


def _translate_and_save(
    lecture_id: int,
    user_id: int,
    source_text: str,
    source_lang: str,
    target_lang: str,
    context: list[str],
    start_offset_ms: int,
    end_offset_ms: int,
) -> tuple[dict | None, dict]:
    translation = translate_with_context(
        source_text, context, source_lang, target_lang
    )
    db = SessionLocal()
    try:
        saved = transcribe_audio(
            db,
            lecture_id,
            user_id,
            source_text,
            translation["text"],
            start_offset_ms=start_offset_ms,
            end_offset_ms=end_offset_ms,
            engine="baidu-realtime",
        )
        return saved, translation
    finally:
        db.close()


@router.websocket("/{lecture_id}/stream")
async def stream_lecture_audio(websocket: WebSocket, lecture_id: int):
    await websocket.accept()
    send_lock = asyncio.Lock()
    client_connected = True

    async def send(payload: dict) -> bool:
        nonlocal client_connected
        if not client_connected:
            return False
        try:
            async with send_lock:
                await websocket.send_json(payload)
            return True
        except (WebSocketDisconnect, RuntimeError):
            client_connected = False
            return False

    async def close(code: int) -> None:
        nonlocal client_connected
        if not client_connected:
            return
        try:
            await websocket.close(code=code)
        except RuntimeError:
            pass
        finally:
            client_connected = False

    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=8)
    except WebSocketDisconnect:
        client_connected = False
        return
    except (asyncio.TimeoutError, ValueError):
        await send({"type": "error", "code": "authentication_required",
                    "message": "实时识别认证超时", "fallback": True})
        await close(4401)
        return

    if auth_message.get("type") != "auth" or not auth_message.get("token"):
        await send({"type": "error", "code": "authentication_required",
                    "message": "实时识别需要登录", "fallback": True})
        await close(4401)
        return

    authenticated = await asyncio.to_thread(
        _authenticate_stream, auth_message["token"], lecture_id
    )
    if not authenticated:
        await send({"type": "error", "code": "authentication_failed",
                    "message": "登录已失效或课堂不存在", "fallback": True})
        await close(4401)
        return

    user_id, source_lang, target_lang = authenticated
    try:
        stream_offset_ms = max(0, int(auth_message.get("offset_ms") or 0))
    except (TypeError, ValueError):
        stream_offset_ms = 0
    if not realtime_is_configured(source_lang):
        await send({
            "type": "unsupported",
            "message": "实时识别未配置或暂不支持该语言，已切换分片识别",
            "fallback": True,
        })
        await close(4403)
        return

    recent_context = await asyncio.to_thread(
        _recent_source_sentences, lecture_id, user_id
    )
    final_queue: asyncio.Queue[dict | None] = asyncio.Queue()
    preview_task: asyncio.Task | None = None
    latest_revision = 0

    async def preview_translation(text: str, utterance_id: str, revision: int):
        try:
            await asyncio.sleep(ASR_REALTIME_PREVIEW_INTERVAL_MS / 1000)
            translation = await asyncio.to_thread(
                translate_with_context,
                text,
                list(recent_context),
                source_lang,
                target_lang,
            )
            if revision != latest_revision:
                return
            await send({
                "type": "preview",
                "utterance_id": utterance_id,
                "revision": revision,
                "source_text": text,
                "translated_text": translation["text"],
                "translation_success": translation["success"],
            })
        except asyncio.CancelledError:
            return

    async def final_worker():
        while True:
            item = await final_queue.get()
            try:
                if item is None:
                    return
                saved, translation = await asyncio.to_thread(
                    _translate_and_save,
                    lecture_id,
                    user_id,
                    item["source_text"],
                    source_lang,
                    target_lang,
                    list(recent_context),
                    item["start_offset_ms"],
                    item["end_offset_ms"],
                )
                if saved:
                    if ASR_CONTEXT_SENTENCES:
                        recent_context.append(item["source_text"])
                        recent_context[:] = recent_context[-ASR_CONTEXT_SENTENCES:]
                    await send({
                        "type": "final",
                        "utterance_id": item["utterance_id"],
                        "revision": item["revision"],
                        "transcription": {
                            **saved,
                            "translation_success": translation["success"],
                            "translation_provider": translation["provider"],
                            "translation_warning": translation["warning"],
                            "context_applied": translation["context_applied"],
                        },
                    })
            except Exception as exc:
                logger.exception("实时识别最终句保存失败: %s", exc)
                await send({
                    "type": "error",
                    "code": "finalization_failed",
                    "message": "当前句保存或翻译失败，请继续录音",
                    "fallback": False,
                })
            finally:
                final_queue.task_done()

    final_worker_task = asyncio.create_task(final_worker())

    try:
        async with connect(
            baidu_stream_url(ASR_REALTIME_URL),
            open_timeout=10,
            close_timeout=5,
            max_size=2 * 1024 * 1024,
            ping_interval=20,
        ) as upstream:
            await upstream.send(json.dumps(baidu_start_frame(
                source_lang, f"livetrans-{user_id}-{uuid.uuid4().hex[:12]}"
            )))
            await send({"type": "ready", "sample_rate": 16000,
                        "frame_duration_ms": 160})

            async def receive_client_audio():
                while True:
                    message = await websocket.receive()
                    if message.get("type") == "websocket.disconnect":
                        try:
                            await upstream.send(json.dumps({"type": "CANCEL"}))
                        except ConnectionClosed:
                            pass
                        raise WebSocketDisconnect()
                    audio = message.get("bytes")
                    if audio is not None:
                        if len(audio) > 64 * 1024:
                            await send({"type": "warning", "code": "frame_too_large",
                                        "message": "实时音频帧过大，已跳过"})
                            continue
                        if audio:
                            await upstream.send(audio)
                        continue
                    raw_text = message.get("text")
                    if not raw_text:
                        continue
                    try:
                        control = json.loads(raw_text)
                    except ValueError:
                        continue
                    if control.get("type") == "finish":
                        await upstream.send(json.dumps({"type": "FINISH"}))
                        return
                    if control.get("type") == "cancel":
                        await upstream.send(json.dumps({"type": "CANCEL"}))
                        return

            async def receive_upstream_results():
                nonlocal preview_task, latest_revision
                async for raw in upstream:
                    if not isinstance(raw, str):
                        continue
                    try:
                        result = json.loads(raw)
                    except ValueError:
                        continue
                    result_type = result.get("type", "")
                    if result_type == "HEARTBEAT":
                        continue
                    error_number = int(result.get("err_no") or 0)
                    if error_number:
                        if is_no_speech_error(error_number):
                            await send({"type": "no_speech"})
                            continue
                        await send({
                            "type": "error",
                            "code": str(error_number),
                            "message": result.get("err_msg") or "实时语音识别失败",
                            "fallback": True,
                        })
                        return
                    text = (result.get("result") or "").strip()
                    if not text:
                        continue
                    latest_revision += 1
                    revision = latest_revision
                    utterance_id = result.get("sn") or f"stream-{revision}"
                    if result_type == "MID_TEXT":
                        await send({
                            "type": "interim",
                            "utterance_id": utterance_id,
                            "revision": revision,
                            "source_text": text,
                        })
                        if preview_task:
                            preview_task.cancel()
                        preview_task = asyncio.create_task(
                            preview_translation(text, utterance_id, revision)
                        )
                    elif result_type == "FIN_TEXT":
                        if preview_task:
                            preview_task.cancel()
                            preview_task = None
                        await send({
                            "type": "finalizing",
                            "utterance_id": utterance_id,
                            "revision": revision,
                            "source_text": text,
                        })
                        await final_queue.put({
                            "utterance_id": utterance_id,
                            "revision": revision,
                            "source_text": text,
                            "start_offset_ms": stream_offset_ms + max(
                                0, int(result.get("start_time") or 0)
                            ),
                            "end_offset_ms": stream_offset_ms + max(
                                0, int(result.get("end_time") or 0)
                            ),
                        })

            client_task = asyncio.create_task(receive_client_audio())
            upstream_task = asyncio.create_task(receive_upstream_results())
            done, _ = await asyncio.wait(
                {client_task, upstream_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if upstream_task in done and not client_task.done():
                client_task.cancel()
            elif client_task in done and not upstream_task.done():
                try:
                    await asyncio.wait_for(upstream_task, timeout=12)
                except asyncio.TimeoutError:
                    upstream_task.cancel()
            for task in (client_task, upstream_task):
                if not task.done():
                    task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, WebSocketDisconnect, ConnectionClosed):
                    pass
    except (OSError, WebSocketException, asyncio.TimeoutError, ValueError) as exc:
        logger.warning("百度实时 ASR 连接失败: %s", exc)
        await send({"type": "error", "code": "upstream_unavailable",
                    "message": "实时识别连接失败，已切换分片识别", "fallback": True})
    finally:
        if preview_task:
            preview_task.cancel()
        await final_queue.join()
        await final_queue.put(None)
        await final_worker_task
        await send({"type": "closed"})
        await close(1000)

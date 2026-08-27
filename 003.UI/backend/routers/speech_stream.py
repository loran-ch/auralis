"""课堂实时语音识别 WebSocket。"""
import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from config import (
    ASR_CONTEXT_SENTENCES,
    ASR_FORCE_FINAL_MS,
    ASR_HISTORY_DOM_LIMIT,
    ASR_MAX_SEGMENT_CHARS,
    ASR_MERGE_MIN_CHARS,
    ASR_MERGE_WAIT_MS,
    ASR_PREVIEW_TRANSLATE_CHARS,
    ASR_REALTIME_PREVIEW_INTERVAL_MS,
    ASR_REALTIME_URL,
)
from database import SessionLocal
from models.lecture import Lecture
from services.asr_segment import (
    distribute_offsets,
    join_segment_parts,
    looks_incomplete,
    preview_translate_tail,
    should_force_finalize,
    split_transcript_segments,
    uncommitted_suffix,
)
from services.auth import authenticate_access_token
from services.lecture import get_recent_source_sentences, transcribe_audio
from services.realtime_speech import (
    aliyun_connect_headers,
    aliyun_finish_task_frame,
    aliyun_run_task_frame,
    aliyun_stream_url,
    baidu_start_frame,
    baidu_stream_url,
    is_no_speech_error,
    parse_aliyun_event,
    realtime_is_configured,
    realtime_provider,
)
from services.translator import translate_with_context


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/lectures", tags=["实时语音识别"])


def _authenticate_stream(token: str, lecture_id: int) -> tuple[int, str, str, bool] | None:
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
        return user.id, lecture.source_lang, lecture.target_lang, bool(lecture.translation_enabled)
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
    translation_enabled: bool,
    context: list[str],
    start_offset_ms: int,
    end_offset_ms: int,
    engine: str = "baidu-realtime",
) -> tuple[dict | None, dict]:
    if translation_enabled:
        translation = translate_with_context(
            source_text, context, source_lang, target_lang
        )
    else:
        translation = {
            "text": source_text,
            "success": True,
            "provider": "disabled",
            "warning": None,
            "context_applied": False,
        }
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
            engine=engine,
        )
        return saved, translation
    finally:
        db.close()


def _ready_payload(provider: str) -> dict:
    return {
        "type": "ready",
        "sample_rate": 16000,
        "frame_duration_ms": 160,
        "provider": provider,
        "max_segment_chars": ASR_MAX_SEGMENT_CHARS,
        "preview_translate_chars": ASR_PREVIEW_TRANSLATE_CHARS,
        "history_dom_limit": ASR_HISTORY_DOM_LIMIT,
        "merge_min_chars": ASR_MERGE_MIN_CHARS,
        "merge_wait_ms": ASR_MERGE_WAIT_MS,
    }


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

    async def close(code: int = 1000):
        nonlocal client_connected
        client_connected = False
        try:
            await websocket.close(code=code)
        except Exception:
            pass

    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=15)
    except WebSocketDisconnect:
        return
    except (asyncio.TimeoutError, ValueError):
        await send({"type": "error", "code": "auth_timeout",
                    "message": "实时识别认证超时", "fallback": True})
        await close(4401)
        return

    if auth_message.get("type") != "auth" or not auth_message.get("token"):
        await send({"type": "error", "code": "auth_required",
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

    user_id, source_lang, target_lang, translation_enabled = authenticated
    try:
        stream_offset_ms = max(0, int(auth_message.get("offset_ms") or 0))
    except (TypeError, ValueError):
        stream_offset_ms = 0
    provider = realtime_provider()
    if not realtime_is_configured(source_lang):
        await send({
            "type": "unsupported",
            "message": "实时识别未配置或暂不支持该语言，已切换分片识别",
            "fallback": True,
        })
        await close(4403)
        return

    engine_name = "aliyun-realtime" if provider == "aliyun" else "baidu-realtime"
    recent_context = await asyncio.to_thread(
        _recent_source_sentences, lecture_id, user_id
    )
    final_queue: asyncio.Queue[dict | None] = asyncio.Queue()
    preview_task: asyncio.Task | None = None
    latest_revision = 0
    committed_prefix = ""
    open_since: float | None = None
    merge_parts: list[str] = []
    merge_start_ms = 0
    merge_end_ms = 0
    merge_utterance_id = ""
    merge_revision = 0
    merge_flush_task: asyncio.Task | None = None

    async def preview_translation(text: str, utterance_id: str, revision: int):
        tail = preview_translate_tail(text, ASR_PREVIEW_TRANSLATE_CHARS)
        if not translation_enabled:
            await send({
                "type": "preview",
                "utterance_id": utterance_id,
                "revision": revision,
                "source_text": text,
                "translated_text": "",
                "translation_success": True,
            })
            return
        try:
            await asyncio.sleep(ASR_REALTIME_PREVIEW_INTERVAL_MS / 1000)
            translation = await asyncio.to_thread(
                translate_with_context,
                tail,
                list(recent_context),
                source_lang,
                target_lang,
            )
            if revision != latest_revision:
                return
            translated = translation["text"]
            if len(text) > ASR_PREVIEW_TRANSLATE_CHARS and translated:
                translated = "…" + translated
            await send({
                "type": "preview",
                "utterance_id": utterance_id,
                "revision": revision,
                "source_text": text,
                "translated_text": translated,
                "translation_success": translation["success"],
            })
        except asyncio.CancelledError:
            return

    async def enqueue_final_text(
        text: str,
        utterance_id: str,
        revision: int,
        start_offset_ms: int,
        end_offset_ms: int,
    ) -> None:
        chunks = split_transcript_segments(text, ASR_MAX_SEGMENT_CHARS)
        if not chunks:
            return
        ranges = distribute_offsets(start_offset_ms, end_offset_ms, len(chunks))
        for index, chunk in enumerate(chunks):
            chunk_start, chunk_end = ranges[index]
            await final_queue.put({
                "utterance_id": f"{utterance_id}-{index}" if len(chunks) > 1 else utterance_id,
                "revision": revision,
                "source_text": chunk,
                "start_offset_ms": chunk_start,
                "end_offset_ms": chunk_end,
            })

    async def flush_merge_buffer() -> None:
        nonlocal merge_parts, merge_flush_task, merge_utterance_id, merge_revision
        nonlocal merge_start_ms, merge_end_ms
        if merge_flush_task and not merge_flush_task.done():
            merge_flush_task.cancel()
            try:
                await merge_flush_task
            except asyncio.CancelledError:
                pass
        merge_flush_task = None
        if not merge_parts:
            return
        text = join_segment_parts(merge_parts)
        utterance_id = merge_utterance_id or f"merge-{latest_revision}"
        revision = merge_revision or latest_revision
        start_ms = merge_start_ms
        end_ms = merge_end_ms
        merge_parts = []
        merge_utterance_id = ""
        merge_revision = 0
        merge_start_ms = 0
        merge_end_ms = 0
        if text:
            await enqueue_final_text(text, utterance_id, revision, start_ms, end_ms)

    async def schedule_merge_flush() -> None:
        nonlocal merge_flush_task
        if merge_flush_task and not merge_flush_task.done():
            merge_flush_task.cancel()
            try:
                await merge_flush_task
            except asyncio.CancelledError:
                pass

        async def _delayed():
            try:
                await asyncio.sleep(ASR_MERGE_WAIT_MS / 1000)
                await flush_merge_buffer()
            except asyncio.CancelledError:
                return

        merge_flush_task = asyncio.create_task(_delayed())

    async def buffer_final_text(
        text: str,
        utterance_id: str,
        revision: int,
        start_offset_ms: int,
        end_offset_ms: int,
        *,
        force: bool = False,
    ) -> None:
        nonlocal merge_parts, merge_utterance_id, merge_revision, merge_start_ms, merge_end_ms
        value = (text or "").strip()
        if not value:
            return
        if force:
            await flush_merge_buffer()
            await enqueue_final_text(
                value, utterance_id, revision, start_offset_ms, end_offset_ms
            )
            return

        if not merge_parts:
            merge_start_ms = start_offset_ms
            merge_utterance_id = utterance_id
            merge_revision = revision
        merge_parts.append(value)
        merge_end_ms = max(merge_end_ms, end_offset_ms)
        merge_revision = revision
        joined = join_segment_parts(merge_parts)
        if len(joined) >= ASR_MAX_SEGMENT_CHARS or not looks_incomplete(
            joined, ASR_MERGE_MIN_CHARS
        ):
            await flush_merge_buffer()
            return
        await schedule_merge_flush()

    async def handle_recognition_text(
        *,
        text: str,
        kind: str,
        utterance_id: str,
        start_offset_ms: int,
        end_offset_ms: int,
    ) -> None:
        nonlocal preview_task, latest_revision, committed_prefix, open_since
        full = (text or "").strip()
        if not full:
            return
        active, committed_prefix = uncommitted_suffix(full, committed_prefix)
        latest_revision += 1
        revision = latest_revision
        display_text = active or full

        if kind == "interim":
            await send({
                "type": "interim",
                "utterance_id": utterance_id,
                "revision": revision,
                "source_text": display_text,
            })
            if preview_task:
                preview_task.cancel()
            if active:
                if open_since is None:
                    open_since = time.monotonic()
                preview_task = asyncio.create_task(
                    preview_translation(active, utterance_id, revision)
                )
                if should_force_finalize(
                    active,
                    max_chars=ASR_MAX_SEGMENT_CHARS,
                    open_since=open_since,
                    now=time.monotonic(),
                    force_ms=ASR_FORCE_FINAL_MS,
                    min_chars=max(24, ASR_MERGE_MIN_CHARS),
                ):
                    if preview_task:
                        preview_task.cancel()
                        preview_task = None
                    await send({
                        "type": "finalizing",
                        "utterance_id": utterance_id,
                        "revision": revision,
                        "source_text": active,
                    })
                    await buffer_final_text(
                        active,
                        utterance_id,
                        revision,
                        start_offset_ms,
                        end_offset_ms,
                        force=True,
                    )
                    committed_prefix = full
                    open_since = None
            return

        # final
        if preview_task:
            preview_task.cancel()
            preview_task = None
        if not active:
            committed_prefix = ""
            open_since = None
            return
        await send({
            "type": "finalizing",
            "utterance_id": utterance_id,
            "revision": revision,
            "source_text": active,
        })
        await buffer_final_text(
            active,
            utterance_id,
            revision,
            start_offset_ms,
            end_offset_ms,
            force=False,
        )
        committed_prefix = ""
        open_since = None

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
                    translation_enabled,
                    list(recent_context),
                    item["start_offset_ms"],
                    item["end_offset_ms"],
                    engine_name,
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
    task_id = uuid.uuid4().hex
    started_event = asyncio.Event()
    client_stopping = False

    try:
        if provider == "aliyun":
            connect_kwargs = {
                "additional_headers": aliyun_connect_headers(),
                "open_timeout": 10,
                "close_timeout": 5,
                "max_size": 2 * 1024 * 1024,
                "ping_interval": 20,
            }
            upstream_url = aliyun_stream_url()
        else:
            connect_kwargs = {
                "open_timeout": 10,
                "close_timeout": 5,
                "max_size": 2 * 1024 * 1024,
                "ping_interval": 20,
            }
            upstream_url = baidu_stream_url(ASR_REALTIME_URL)

        async with connect(upstream_url, **connect_kwargs) as upstream:
            if provider == "aliyun":
                await upstream.send(json.dumps(
                    aliyun_run_task_frame(source_lang, task_id=task_id)
                ))
            else:
                await upstream.send(json.dumps(baidu_start_frame(
                    source_lang, f"livetrans-{user_id}-{uuid.uuid4().hex[:12]}"
                )))
                started_event.set()
                await send(_ready_payload(provider))

            async def restart_aliyun_task(reason: str) -> bool:
                """老师停顿导致上游结束任务时，同连接再开一轮，避免前端掉进降级模式。"""
                nonlocal task_id, client_stopping
                if client_stopping or provider != "aliyun":
                    return False
                task_id = uuid.uuid4().hex
                started_event.clear()
                try:
                    await upstream.send(json.dumps(
                        aliyun_run_task_frame(source_lang, task_id=task_id)
                    ))
                except ConnectionClosed:
                    return False
                await send({
                    "type": "info",
                    "code": "asr_task_resumed",
                    "message": reason,
                    "fallback": False,
                })
                return True

            async def receive_client_audio():
                nonlocal client_stopping
                while True:
                    message = await websocket.receive()
                    if message.get("type") == "websocket.disconnect":
                        client_stopping = True
                        try:
                            if provider == "aliyun":
                                await upstream.send(json.dumps(
                                    aliyun_finish_task_frame(task_id)
                                ))
                            else:
                                await upstream.send(json.dumps({"type": "CANCEL"}))
                        except ConnectionClosed:
                            pass
                        raise WebSocketDisconnect()
                    audio = message.get("bytes")
                    if audio is not None:
                        if provider == "aliyun" and not started_event.is_set():
                            try:
                                await asyncio.wait_for(started_event.wait(), timeout=8)
                            except asyncio.TimeoutError:
                                await send({
                                    "type": "error",
                                    "code": "upstream_not_ready",
                                    "message": "阿里实时识别未就绪，已切换分片识别",
                                    "fallback": True,
                                })
                                return
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
                        client_stopping = True
                        if provider == "aliyun":
                            await upstream.send(json.dumps(
                                aliyun_finish_task_frame(task_id)
                            ))
                        else:
                            await upstream.send(json.dumps({"type": "FINISH"}))
                        return
                    if control.get("type") == "cancel":
                        client_stopping = True
                        if provider == "aliyun":
                            await upstream.send(json.dumps(
                                aliyun_finish_task_frame(task_id)
                            ))
                        else:
                            await upstream.send(json.dumps({"type": "CANCEL"}))
                        return

            async def receive_upstream_results():
                nonlocal preview_task
                async for raw in upstream:
                    if not isinstance(raw, str):
                        continue
                    try:
                        result = json.loads(raw)
                    except ValueError:
                        continue

                    if provider == "aliyun":
                        event = parse_aliyun_event(result)
                        kind = event.get("kind")
                        if kind == "started":
                            if not started_event.is_set():
                                started_event.set()
                                await send(_ready_payload(provider))
                            continue
                        if kind in {"heartbeat", "ignore"}:
                            continue
                        if kind == "finished":
                            if client_stopping:
                                return
                            resumed = await restart_aliyun_task(
                                "识别连接已自动续上，可继续讲课"
                            )
                            if not resumed:
                                return
                            continue
                        if kind == "failed":
                            if client_stopping:
                                return
                            # 失败任务不能复用连接：通知前端重连，而不是立刻演示/分片。
                            await send({
                                "type": "error",
                                "code": "aliyun_asr_failed",
                                "message": event.get("message") or "阿里实时识别中断，正在重连",
                                "fallback": False,
                                "reconnect": True,
                            })
                            return
                        text = (event.get("text") or "").strip()
                        if not text:
                            continue
                        utterance_id = event.get("utterance_id") or f"stream-{latest_revision + 1}"
                        await handle_recognition_text(
                            text=text,
                            kind="interim" if kind == "interim" else "final",
                            utterance_id=utterance_id,
                            start_offset_ms=stream_offset_ms + max(
                                0, int(event.get("start_offset_ms") or 0)
                            ),
                            end_offset_ms=stream_offset_ms + max(
                                0, int(event.get("end_offset_ms") or 0)
                            ),
                        )
                        continue

                    # 百度协议
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
                    utterance_id = result.get("sn") or f"stream-{latest_revision + 1}"
                    if result_type == "MID_TEXT":
                        await handle_recognition_text(
                            text=text,
                            kind="interim",
                            utterance_id=utterance_id,
                            start_offset_ms=stream_offset_ms + max(
                                0, int(result.get("start_time") or 0)
                            ),
                            end_offset_ms=stream_offset_ms + max(
                                0, int(result.get("end_time") or 0)
                            ),
                        )
                    elif result_type == "FIN_TEXT":
                        await handle_recognition_text(
                            text=text,
                            kind="final",
                            utterance_id=utterance_id,
                            start_offset_ms=stream_offset_ms + max(
                                0, int(result.get("start_time") or 0)
                            ),
                            end_offset_ms=stream_offset_ms + max(
                                0, int(result.get("end_time") or 0)
                            ),
                        )

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
        logger.warning("%s 实时 ASR 连接失败: %s", provider, exc)
        await send({"type": "error", "code": "upstream_unavailable",
                    "message": "实时识别连接失败，正在尝试重连",
                    "fallback": False, "reconnect": True})
    finally:
        if preview_task:
            preview_task.cancel()
        try:
            await flush_merge_buffer()
        except Exception:
            logger.exception("flush merge buffer failed")
        await final_queue.put(None)
        try:
            await asyncio.wait_for(final_worker_task, timeout=20)
        except asyncio.TimeoutError:
            final_worker_task.cancel()
        await send({"type": "closed"})
        await close()

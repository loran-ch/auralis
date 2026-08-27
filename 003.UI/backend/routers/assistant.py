"""独立学习助手：会话持久化、范围校验与课程级证据问答。"""
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from config import MAX_ATTACHMENT_SIZE_MB
from database import SessionLocal, get_db
from models.lecture import AssistantMessage, AssistantThread, Lecture
from models.user import User
from routers.auth import get_current_user
from schemas.assistant import (AssistantAskThreadReq, AssistantAskThreadResp,
                               AssistantMessageResp, AssistantScreenshotResp,
                               AssistantThreadCreate, AssistantThreadDetailResp,
                               AssistantThreadResp)
from services.assistant import answer_scope_question, stream_scope_question
from services.assistant_images import (ASSISTANT_UPLOAD_DIR, build_image_url,
                                       compose_question_with_screenshot,
                                       is_owned_assistant_image,
                                       local_path_for_url)
from services.courses import get_readable_course
from services.image_ocr import detect_image_extension, ocr_image_path


router = APIRouter(prefix="/api/assistant", tags=["学习助手"])
_MAX_CONTEXT_MESSAGES = 6
_MAX_SCREENSHOT_BYTES = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024


def _sse(event: str, payload: dict) -> bytes:
    """把服务端事件序列化为浏览器可消费的 UTF-8 SSE 帧。"""
    data = json.dumps(jsonable_encoder(payload), ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n".encode("utf-8")


def _user_or_401(user: Optional[User]) -> User:
    if not user:
        raise HTTPException(401, "请先登录")
    return user


def _thread_or_404(db: Session, user_id: int, thread_id: int) -> AssistantThread:
    thread = db.query(AssistantThread).filter(
        AssistantThread.id == thread_id, AssistantThread.user_id == user_id,
    ).first()
    if not thread:
        raise HTTPException(404, "学习会话不存在")
    return thread


def _normal_ids(values) -> list[int]:
    result = []
    for value in values or []:
        try:
            value = int(value)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in result:
            result.append(value)
    return result


def _scope_lectures(db: Session, viewer: User, course_id: Optional[int], lecture_ids: list[int]) -> list[Lecture]:
    """课主可读自己的课；其他用户仅可读公开课主的已完成课次。"""
    content_user_id = viewer.id
    if course_id:
        course = get_readable_course(db, viewer, course_id)
        if not course:
            raise HTTPException(404, "课程不存在或无权访问")
        content_user_id = int(course.user_id)

    query = db.query(Lecture).filter(
        Lecture.user_id == content_user_id, Lecture.status == "completed",
    )
    if lecture_ids:
        rows = query.filter(Lecture.id.in_(lecture_ids)).order_by(
            Lecture.lecture_date.asc(), Lecture.started_at.asc(), Lecture.id.asc()
        ).all()
        if len(rows) != len(lecture_ids):
            raise HTTPException(422, "选择的课次不存在、未完成或无权访问")
        if course_id and any(row.course_id != course_id for row in rows):
            raise HTTPException(422, "所选课次不属于当前课程")
        return rows
    if course_id:
        return query.filter(Lecture.course_id == course_id).order_by(
            Lecture.lecture_date.asc(), Lecture.started_at.asc(), Lecture.id.asc()
        ).all()
    raise HTTPException(422, "请选择一门课程或至少一节课")


def _make_summary(db: Session, thread: AssistantThread) -> Optional[str]:
    """本地压缩长期上下文，避免每轮把所有历史对话交给模型。"""
    questions = db.query(AssistantMessage.content).filter(
        AssistantMessage.thread_id == thread.id, AssistantMessage.role == "user",
    ).order_by(AssistantMessage.id.desc()).limit(8).all()
    if not questions:
        return None
    items = [str(row[0]).strip()[:100] for row in reversed(questions) if str(row[0]).strip()]
    return "已讨论：" + "；".join(items)


def _thread_resp(db: Session, thread: AssistantThread) -> AssistantThreadResp:
    last = db.query(AssistantMessage.content).filter(
        AssistantMessage.thread_id == thread.id,
    ).order_by(AssistantMessage.id.desc()).first()
    return AssistantThreadResp(
        id=thread.id,
        course_id=thread.course_id,
        lecture_ids=_normal_ids(thread.lecture_ids),
        title=thread.title,
        summary=thread.summary,
        last_message_preview=(str(last[0])[:100] if last else ""),
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


@router.get("/threads", response_model=list[AssistantThreadResp])
def list_threads(course_id: Optional[int] = Query(None, gt=0), user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    user = _user_or_401(user)
    query = db.query(AssistantThread).filter(AssistantThread.user_id == user.id)
    if course_id:
        query = query.filter(AssistantThread.course_id == course_id)
    rows = query.order_by(AssistantThread.updated_at.desc(), AssistantThread.id.desc()).limit(100).all()
    return [_thread_resp(db, row) for row in rows]


@router.post("/threads", response_model=AssistantThreadResp, status_code=201)
def create_thread(request: AssistantThreadCreate, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    user = _user_or_401(user)
    if request.course_id and not get_readable_course(db, user, request.course_id):
        raise HTTPException(404, "课程不存在或无权访问")
    lecture_ids = _normal_ids(request.lecture_ids)
    _scope_lectures(db, user, request.course_id, lecture_ids)
    thread = AssistantThread(
        user_id=user.id,
        course_id=request.course_id,
        lecture_ids=lecture_ids,
        title=request.title or "新学习会话",
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return _thread_resp(db, thread)


@router.get("/threads/{thread_id}", response_model=AssistantThreadDetailResp)
def get_thread(thread_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _user_or_401(user)
    thread = _thread_or_404(db, user.id, thread_id)
    base = _thread_resp(db, thread).model_dump()
    messages = db.query(AssistantMessage).filter(
        AssistantMessage.thread_id == thread.id,
    ).order_by(AssistantMessage.id.asc()).limit(200).all()
    base["messages"] = [AssistantMessageResp(
        id=row.id, role=row.role, content=row.content, citations=row.citations or [], created_at=row.created_at,
    ) for row in messages]
    return AssistantThreadDetailResp(**base)


@router.delete("/threads/{thread_id}", status_code=204)
def delete_thread(thread_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _user_or_401(user)
    thread = _thread_or_404(db, user.id, thread_id)
    db.delete(thread)
    db.commit()


@router.post("/threads/{thread_id}/screenshots", response_model=AssistantScreenshotResp, status_code=201)
async def upload_thread_screenshot(thread_id: int, file: UploadFile = File(...),
                                   user: User = Depends(get_current_user),
                                   db: Session = Depends(get_db)):
    """上传提问截图并做 OCR，供后续 ask/stream 引用。"""
    user = _user_or_401(user)
    _thread_or_404(db, user.id, thread_id)
    header = await file.read(32)
    if not header:
        raise HTTPException(422, "空文件")
    ext = detect_image_extension(header, file.content_type)
    if not ext:
        raise HTTPException(422, "仅支持 jpg / png / webp 截图")
    rest = await file.read(_MAX_SCREENSHOT_BYTES + 1)
    payload = header + rest
    if len(payload) > _MAX_SCREENSHOT_BYTES:
        raise HTTPException(422, f"截图不能超过 {MAX_ATTACHMENT_SIZE_MB}MB")

    ASSISTANT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{user.id}_{thread_id}_{uuid.uuid4().hex[:12]}{ext}"
    path = ASSISTANT_UPLOAD_DIR / filename
    path.write_bytes(payload)
    ocr = ocr_image_path(path)
    return AssistantScreenshotResp(
        url=build_image_url(user.id, filename),
        ocr_text=ocr.get("ocr_text") or "",
        ocr_confidence=float(ocr.get("ocr_confidence") or 0),
        ocr_status=ocr.get("ocr_status") or "failed",
        error_message=ocr.get("error_message"),
    )


def _prepare_ask_question(user_id: int, request: AssistantAskThreadReq) -> tuple[str, str, list, str]:
    """校验截图归属，返回 (展示问题, 模型问题, 用户消息 citations, ocr文本)。"""
    image_url = request.image_url
    image_ocr = request.image_ocr or ""
    if image_url:
        if not is_owned_assistant_image(image_url, user_id):
            raise HTTPException(422, "截图不属于当前用户")
        path = local_path_for_url(image_url)
        try:
            path.relative_to(ASSISTANT_UPLOAD_DIR.resolve())
        except ValueError:
            raise HTTPException(422, "截图路径非法")
        if not path.is_file():
            raise HTTPException(422, "截图文件不存在，请重新上传")
        if not image_ocr:
            image_ocr = ocr_image_path(path).get("ocr_text") or ""
    display, enriched = compose_question_with_screenshot(request.question, image_ocr)
    citations = []
    if image_url:
        citations.append({
            "type": "image",
            "url": image_url,
            "ocr_text": (image_ocr or "")[:500],
        })
    return display, enriched, citations, image_ocr


@router.post("/threads/{thread_id}/ask", response_model=AssistantAskThreadResp)
def ask_thread(thread_id: int, request: AssistantAskThreadReq,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _user_or_401(user)
    thread = _thread_or_404(db, user.id, thread_id)
    lecture_ids = _normal_ids(thread.lecture_ids)
    lectures = _scope_lectures(db, user, thread.course_id, lecture_ids)
    display_question, model_question, image_citations, _image_ocr = _prepare_ask_question(user.id, request)

    context_rows = db.query(AssistantMessage).filter(
        AssistantMessage.thread_id == thread.id,
    ).order_by(AssistantMessage.id.desc()).limit(_MAX_CONTEXT_MESSAGES).all()
    history = [{"role": row.role, "content": row.content} for row in reversed(context_rows)]
    db.add(AssistantMessage(
        thread_id=thread.id, user_id=user.id, role="user",
        content=display_question, citations=image_citations or None,
    ))
    if thread.title == "新学习会话":
        thread.title = display_question[:80]
    db.flush()

    course = get_readable_course(db, user, thread.course_id) if thread.course_id else None
    scope_name = course.name if course else "指定课堂记录"
    result = answer_scope_question(
        db, lectures, user.id, model_question, scope_name=scope_name,
        history=history, summary=thread.summary or "",
    )
    db.add(AssistantMessage(
        thread_id=thread.id, user_id=user.id, role="assistant",
        content=result["answer"], citations=result.get("citations") or [],
    ))
    thread.summary = _make_summary(db, thread)
    thread.updated_at = datetime.now()
    db.commit()
    db.refresh(thread)
    return AssistantAskThreadResp(
        answer=result["answer"], citations=result.get("citations") or [],
        provider=result.get("provider", "extractive"), thread=_thread_resp(db, thread),
    )


@router.post("/threads/{thread_id}/ask/stream")
def ask_thread_stream(thread_id: int, request: AssistantAskThreadReq,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """流式输出课堂助手回答；最终答案与已校验引用仍会持久化。"""
    user = _user_or_401(user)
    thread = _thread_or_404(db, user.id, thread_id)
    lecture_ids = _normal_ids(thread.lecture_ids)
    lectures = _scope_lectures(db, user, thread.course_id, lecture_ids)
    display_question, model_question, image_citations, image_ocr = _prepare_ask_question(user.id, request)
    history_rows = db.query(AssistantMessage).filter(
        AssistantMessage.thread_id == thread.id,
    ).order_by(AssistantMessage.id.desc()).limit(_MAX_CONTEXT_MESSAGES).all()
    history = [{"role": row.role, "content": row.content} for row in reversed(history_rows)]
    lecture_scope_ids = [int(lecture.id) for lecture in lectures]
    course = get_readable_course(db, user, thread.course_id) if thread.course_id else None
    scope_name = course.name if course else "指定课堂记录"
    user_id = int(user.id)
    thread_summary = thread.summary or ""
    ask_hint = request.hint
    ask_assignment_id = request.assignment_id

    db.add(AssistantMessage(
        thread_id=thread.id, user_id=user.id, role="user",
        content=display_question, citations=image_citations or None,
    ))
    if thread.title == "新学习会话":
        thread.title = display_question[:80]
    db.commit()

    def event_stream():
        stream_db = SessionLocal()
        try:
            yield _sse("meta", {"thread_id": thread_id, "provider": "streaming"})
            for event in stream_scope_question(
                stream_db, lecture_scope_ids, user_id, model_question,
                scope_name=scope_name, history=history, summary=thread_summary,
                hint=ask_hint, assignment_id=ask_assignment_id,
                image_ocr=image_ocr,
            ):
                event_type = event.get("type")
                if event_type == "tool_start":
                    yield _sse("tool_start", {
                        "tool": event.get("tool"),
                        "arguments": event.get("arguments") or {},
                    })
                    continue
                if event_type == "tool_result":
                    yield _sse("tool_result", {
                        "tool": event.get("tool"),
                        "result": event.get("result") or {},
                    })
                    continue
                if event_type == "delta":
                    yield _sse("delta", {"content": event["content"]})
                    continue

                result = event["result"]
                persisted_thread = _thread_or_404(stream_db, user_id, thread_id)
                stream_db.add(AssistantMessage(
                    thread_id=persisted_thread.id,
                    user_id=user_id,
                    role="assistant",
                    content=result["answer"],
                    citations=result.get("citations") or [],
                ))
                persisted_thread.summary = _make_summary(stream_db, persisted_thread)
                persisted_thread.updated_at = datetime.now()
                stream_db.commit()
                stream_db.refresh(persisted_thread)
                yield _sse("done", {
                    "answer": result["answer"],
                    "citations": result.get("citations") or [],
                    "provider": result.get("provider", "extractive"),
                    "tools_used": result.get("tools_used") or [],
                    "thread": _thread_resp(stream_db, persisted_thread).model_dump(mode="json"),
                })
        except Exception:
            stream_db.rollback()
            yield _sse("error", {"message": "课堂助手流式回答失败，请重试。"})
        finally:
            stream_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

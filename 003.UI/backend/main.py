"""LiveTrans Voice — FastAPI 入口"""
from pathlib import Path
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
import uvicorn

from config import (HOST, PORT, DEBUG, CORS_ORIGINS, CORS_ORIGIN_REGEX, ENABLE_DOCS,
                    ENVIRONMENT, IS_PRODUCTION)
from database import engine
from routers.auth import router as auth_router
from routers.lecture import router as lecture_router
from routers.bookmark import router as bookmark_router
from routers.translate import router as translate_router
from routers.preferences import router as preferences_router
from routers.admin import router as admin_router
from routers.speech_stream import router as speech_stream_router
from routers.guide import router as guide_router

app = FastAPI(
    title="LiveTrans Voice API",
    version="1.3.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ORIGINS),
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "")
    if not request_id or len(request_id) > 128:
        request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    started_at = time.perf_counter()
    if IS_PRODUCTION and request.url.path in {
        "/html/auto-login.html",
        "/html/test-history.html",
        "/html/test-recorder.html",
    }:
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = str(
        round((time.perf_counter() - started_at) * 1000, 2)
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=(self)"
    if request.url.path == "/" or request.url.path.startswith(("/html/", "/js/", "/shared/")):
        # 原型阶段没有构建产物哈希，强制协商缓存以避免旧脚本破坏 API 兼容性。
        response.headers["Cache-Control"] = "no-cache"
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(auth_router)
app.include_router(lecture_router)
app.include_router(bookmark_router)
app.include_router(translate_router)
app.include_router(preferences_router)
app.include_router(admin_router)
app.include_router(speech_stream_router)
app.include_router(guide_router)


@app.get("/health/live", include_in_schema=False)
def health_live():
    return {"status": "ok", "environment": ENVIRONMENT}


@app.get("/health/ready", include_in_schema=False)
def health_ready():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)


@app.get("/", include_in_schema=False)
def landing_page():
    return RedirectResponse("/html/recorder.html", status_code=307)

# 前端静态文件 — 按子目录分别挂载，避免 root mount 拦截 API 路由
frontend = Path(__file__).resolve().parent.parent / "frontend"
if frontend.exists():
    for sub in ("css", "js", "html", "shared", "uploads", "screens"):
        sub_dir = frontend / sub
        if sub_dir.is_dir():
            app.mount(f"/{sub}", StaticFiles(directory=str(sub_dir), html=(sub == "html")), name=f"frontend_{sub}")

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=DEBUG)

"""
LiveTrans v1.01 — FastAPI 应用入口
===============================
启动方式:
  python main.py
或:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload

API 文档:
  http://localhost:8000/docs      (Swagger)
  http://localhost:8000/redoc     (ReDoc)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from config import CORS_ORIGINS, DEBUG, HOST, PORT
from routers.auth import router as auth_router

app = FastAPI(
    title="LiveTrans API",
    description="摄像头实时翻译 — 后端服务 v1.01",
    version="1.0.1",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)

# 前端静态文件 (../frontend → http://localhost:8000/)
frontend_path = Path(__file__).resolve().parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
    print(f"[LiveTrans] 前端文件已挂载: {frontend_path}")
else:
    print(f"[LiveTrans] 警告: 前端目录不存在: {frontend_path}")


@app.get("/api/health")
def health_check():
    """健康检查"""
    return {"status": "ok", "version": "1.0.1", "service": "LiveTrans API"}


# ─── 启动入口 ───────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print(f"""
╔══════════════════════════════════════════════╗
║       LiveTrans API v1.01                    ║
║       http://{HOST}:{PORT}                      ║
║       API 文档: http://{HOST}:{PORT}/docs        ║
║       前端首页: http://{HOST}:{PORT}/            ║
╚══════════════════════════════════════════════╝
    """)
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info",
    )

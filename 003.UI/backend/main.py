"""LiveTrans Voice — FastAPI 入口"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from config import HOST, PORT, DEBUG
from routers.auth import router as auth_router
from routers.lecture import router as lecture_router
from routers.bookmark import router as bookmark_router
from routers.translate import router as translate_router

app = FastAPI(title="LiveTrans Voice API", version="1.2.0", docs_url="/docs")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth_router)
app.include_router(lecture_router)
app.include_router(bookmark_router)
app.include_router(translate_router)

# 前端静态文件
frontend = Path(__file__).resolve().parent.parent / "frontend"
if frontend.exists():
    app.mount("/", StaticFiles(directory=str(frontend), html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT, reload=DEBUG)

"""LiveTrans Voice — 应用配置"""
import os

DATABASE_URL = os.getenv("DATABASE_URL",
    "mysql+pymysql://root:root123@127.0.0.1:13306/livetrans_voice?charset=utf8mb4")

JWT_SECRET      = os.getenv("JWT_SECRET", "livetrans-voice-dev-secret")
JWT_ALGORITHM   = "HS256"
ACCESS_EXPIRE_DAYS  = 7
REFRESH_EXPIRE_DAYS = 30

CODE_LENGTH       = 6
CODE_EXPIRE_SEC   = 300
CODE_RESEND_SEC   = 60
CODE_DAILY_LIMIT  = 10

HOST  = os.getenv("HOST", "0.0.0.0")
PORT  = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

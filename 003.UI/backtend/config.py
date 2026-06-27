"""
LiveTrans — 应用配置
"""
import os

# 数据库 (连接你已建好的 MySQL)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:root123@127.0.0.1:13306/livetrans?charset=utf8mb4"
)

# JWT — PRD §4.7.3: Access Token 7天, Refresh Token 30天
JWT_SECRET = os.getenv("JWT_SECRET", "livetrans-dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7
REFRESH_TOKEN_EXPIRE_DAYS = 30

# 验证码
VERIFICATION_CODE_LENGTH = 6
VERIFICATION_CODE_EXPIRE_SECONDS = 300        # 5分钟
VERIFICATION_CODE_RESEND_SECONDS = 60         # 60秒后可重发
VERIFICATION_CODE_DAILY_LIMIT = 10            # 每天上限

# 服务器
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# CORS — 允许前端跨域
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "*",
]

"""LiveTrans Voice — 应用配置。

开发环境提供可运行的本地默认值；生产环境必须显式提供敏感配置，
避免因遗漏环境变量而使用公开的开发密钥。

直接在 .env 文件中填写 API Key 即可生效，不需要改代码。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))


ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

_DEV_DATABASE_URL = (
    "mysql+pymysql://root:root123@127.0.0.1:13306/"
    "livetrans_voice?charset=utf8mb4"
)
_DEV_JWT_SECRET = "livetrans-voice-dev-secret-change-me"

DATABASE_URL = os.getenv("DATABASE_URL", _DEV_DATABASE_URL)
JWT_SECRET = os.getenv("JWT_SECRET", _DEV_JWT_SECRET)
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
DB_POOL_TIMEOUT_SECONDS = int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "10"))
DB_POOL_RECYCLE_SECONDS = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))

if IS_PRODUCTION and DATABASE_URL == _DEV_DATABASE_URL:
    raise RuntimeError("生产环境必须配置 DATABASE_URL")
if IS_PRODUCTION and (JWT_SECRET == _DEV_JWT_SECRET or len(JWT_SECRET) < 32):
    raise RuntimeError("生产环境必须配置至少 32 字符的强随机 JWT_SECRET")

JWT_ALGORITHM = "HS256"
ACCESS_EXPIRE_MINUTES = int(os.getenv("ACCESS_EXPIRE_MINUTES", "15"))
REFRESH_EXPIRE_DAYS = int(os.getenv("REFRESH_EXPIRE_DAYS", "30"))
if ACCESS_EXPIRE_MINUTES <= 0 or REFRESH_EXPIRE_DAYS <= 0:
    raise RuntimeError("令牌有效期必须为正整数")
if min(DB_POOL_SIZE, DB_POOL_TIMEOUT_SECONDS, DB_POOL_RECYCLE_SECONDS) <= 0:
    raise RuntimeError("数据库连接池参数必须为正整数")

CODE_LENGTH       = 6
CODE_EXPIRE_SEC   = 300
CODE_RESEND_SEC   = 60
CODE_DAILY_LIMIT  = 10

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false" if IS_PRODUCTION else "true").lower() == "true"

_DEFAULT_CORS = (
    "http://127.0.0.1:8001,http://localhost:8001,"
    "http://127.0.0.1:5173,http://localhost:5173,"
    "http://127.0.0.1:5190,http://localhost:5190"
)
CORS_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "" if IS_PRODUCTION else _DEFAULT_CORS
    ).split(",")
    if origin.strip()
)
if IS_PRODUCTION and "*" in CORS_ORIGINS:
    raise RuntimeError("生产环境的 CORS_ORIGINS 不能使用通配符")

# 开发时允许由同一局域网中的真机或 Android 模拟器打开 Vite H5 页面。
# 生产环境关闭该规则，只接受 CORS_ORIGINS 中显式配置的 HTTPS 来源。
CORS_ORIGIN_REGEX = None if IS_PRODUCTION else (
    r"^https?://(?:localhost|127\.0\.0\.1|\[::1\]|"
    r"10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})"
    r"(?::\d{1,5})?$"
)

ENABLE_DOCS = os.getenv("ENABLE_DOCS", "false" if IS_PRODUCTION else "true").lower() == "true"

TRANSLATION_PROVIDER_ORDER = tuple(
    provider.strip().lower()
    for provider in os.getenv("TRANSLATION_PROVIDER_ORDER", "google,mymemory").split(",")
    if provider.strip()
)
if not TRANSLATION_PROVIDER_ORDER:
    import warnings
    warnings.warn("没有可用的翻译服务，翻译将保留原文")
elif any(
    provider not in {"enterprise", "google", "mymemory", "baidu"}
    for provider in TRANSLATION_PROVIDER_ORDER
):
    raise RuntimeError("TRANSLATION_PROVIDER_ORDER 仅支持 enterprise、google、mymemory 和 baidu")
ENTERPRISE_TRANSLATION_API_URL = os.getenv(
    "ENTERPRISE_TRANSLATION_API_URL", ""
).strip()
ENTERPRISE_TRANSLATION_API_KEY = os.getenv(
    "ENTERPRISE_TRANSLATION_API_KEY", ""
).strip()
if "enterprise" in TRANSLATION_PROVIDER_ORDER and not ENTERPRISE_TRANSLATION_API_URL:
    raise RuntimeError("启用 enterprise 翻译时必须配置 ENTERPRISE_TRANSLATION_API_URL")
GOOGLE_TRANSLATE_API_URL = os.getenv(
    "GOOGLE_TRANSLATE_API_URL", "https://translate.googleapis.com/translate_a/single"
)
MYMEMORY_API_URL = os.getenv(
    "MYMEMORY_API_URL",
    os.getenv("TRANSLATION_API_URL", "https://api.mymemory.translated.net/get"),
)
BAIDU_TRANSLATE_APP_ID = os.getenv("BAIDU_TRANSLATE_APP_ID", "").strip()
BAIDU_TRANSLATE_SECRET_KEY = os.getenv("BAIDU_TRANSLATE_SECRET_KEY", "").strip()
BAIDU_TRANSLATE_API_URL = os.getenv(
    "BAIDU_TRANSLATE_API_URL",
    "https://fanyi-api.baidu.com/api/trans/vip/translate",
)
if "baidu" in TRANSLATION_PROVIDER_ORDER and not (BAIDU_TRANSLATE_APP_ID and BAIDU_TRANSLATE_SECRET_KEY):
    import warnings
    warnings.warn("TRANSLATION_PROVIDER_ORDER 包含 baidu 但未配置 APP_ID/SECRET_KEY，翻译将保留原文")
    TRANSLATION_PROVIDER_ORDER = tuple(
        p for p in TRANSLATION_PROVIDER_ORDER if p != "baidu"
    )
TRANSLATION_TIMEOUT_SECONDS = float(os.getenv("TRANSLATION_TIMEOUT_SECONDS", "3"))
TRANSLATION_CACHE_TTL_SECONDS = int(os.getenv("TRANSLATION_CACHE_TTL_SECONDS", "3600"))
if TRANSLATION_TIMEOUT_SECONDS <= 0 or TRANSLATION_CACHE_TTL_SECONDS < 0:
    raise RuntimeError("翻译超时必须大于 0，缓存时间不能为负数")

# 兼容常见 multipart 语音转文字服务。留空时客户端会明确进入演示降级，
# 生产环境应通过密钥管理服务注入地址和凭据。
# ─── 语音识别 API ─────────────────────────────────────
# 在这里直接填写你的 API Key，留空则使用演示模式
ASR_API_URL = os.getenv("ASR_API_URL", "").strip()     # ← 填服务商地址
ASR_API_KEY = os.getenv("ASR_API_KEY", "").strip()     # ← 填 API Key（百度需配合 SECRET）
ASR_API_SECRET = os.getenv("ASR_API_SECRET", "").strip()  # ← 百度 Secret Key
ASR_MODEL = os.getenv("ASR_MODEL", "").strip()         # ← 填模型名称

# ─── 企业翻译 API（可选）──────────────────────────────
# 如果要用付费翻译服务，在这里填写
ENTERPRISE_TRANSLATION_API_URL = os.getenv("ENTERPRISE_TRANSLATION_API_URL", "").strip()  # ← 翻译 API 地址
ENTERPRISE_TRANSLATION_API_KEY = os.getenv("ENTERPRISE_TRANSLATION_API_KEY", "").strip()  # ← 翻译 API Key
ASR_TIMEOUT_SECONDS = float(os.getenv("ASR_TIMEOUT_SECONDS", "20"))
ASR_MAX_SEGMENT_MB = int(os.getenv("ASR_MAX_SEGMENT_MB", "10"))
if ASR_TIMEOUT_SECONDS <= 0 or ASR_MAX_SEGMENT_MB <= 0:
    raise RuntimeError("ASR 超时和分片大小必须为正数")
if IS_PRODUCTION and not ASR_API_URL:
    raise RuntimeError("生产环境必须配置 ASR_API_URL")

MAX_AVATAR_SIZE_MB = int(os.getenv("MAX_AVATAR_SIZE_MB", "2"))
MAX_AUDIO_SIZE_MB = int(os.getenv("MAX_AUDIO_SIZE_MB", "100"))

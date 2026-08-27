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
# 强制 utf8mb4 连接，避免中文 / emoji（4 字节）在缺失 charset 参数时乱码
if "charset=" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = f"{DATABASE_URL}{sep}charset=utf8mb4"
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

MAX_VIDEO_SIZE_MB = int(os.getenv("MAX_VIDEO_SIZE_MB", "1024"))
if MAX_VIDEO_SIZE_MB <= 0:
    raise RuntimeError("MAX_VIDEO_SIZE_MB 必须为正整数")

MAX_ATTACHMENT_SIZE_MB = int(os.getenv("MAX_ATTACHMENT_SIZE_MB", "10"))
if MAX_ATTACHMENT_SIZE_MB <= 0:
    raise RuntimeError("MAX_ATTACHMENT_SIZE_MB 必须为正整数")

MAX_MATERIAL_SIZE_MB = int(os.getenv("MAX_MATERIAL_SIZE_MB", "50"))
if MAX_MATERIAL_SIZE_MB <= 0:
    raise RuntimeError("MAX_MATERIAL_SIZE_MB 必须为正整数")

# 生产环境应显式配置容器内路径；开发环境默认使用项目的语言模型目录。
FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "ffmpeg").strip()
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract").strip()
TESSDATA_DIR = os.getenv("TESSDATA_DIR", str(Path(__file__).with_name("tessdata"))).strip()
OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "chi_sim+eng").strip()

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
# ASR_PROVIDER=baidu|aliyun；实时字幕走对应上游，分片降级仍可用百度/通用 multipart。
ASR_PROVIDER = os.getenv("ASR_PROVIDER", "baidu").strip().lower() or "baidu"
if ASR_PROVIDER not in {"baidu", "aliyun"}:
    raise RuntimeError("ASR_PROVIDER 仅支持 baidu 或 aliyun")
ASR_API_URL = os.getenv("ASR_API_URL", "").strip()     # ← 填服务商地址
ASR_API_KEY = os.getenv("ASR_API_KEY", "").strip()     # ← 填 API Key（百度需配合 SECRET）
ASR_API_SECRET = os.getenv("ASR_API_SECRET", "").strip()  # ← 百度 Secret Key
ASR_APP_ID = os.getenv("ASR_APP_ID", "").strip()       # ← 百度实时识别需要 App ID
ASR_MODEL = os.getenv("ASR_MODEL", "").strip()         # ← 填模型名称
ASR_REALTIME_URL = os.getenv(
    "ASR_REALTIME_URL", "wss://vop.baidu.com/realtime_asr"
).strip()
# 阿里云百炼实时 ASR（Fun-ASR / Paraformer）
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
ASR_ALIYUN_REALTIME_URL = os.getenv(
    "ASR_ALIYUN_REALTIME_URL",
    "wss://dashscope.aliyuncs.com/api-ws/v1/inference",
).strip()
ASR_ALIYUN_MODEL = os.getenv(
    "ASR_ALIYUN_MODEL", "fun-asr-realtime"
).strip() or "fun-asr-realtime"
ASR_REALTIME_PREVIEW_INTERVAL_MS = int(
    os.getenv("ASR_REALTIME_PREVIEW_INTERVAL_MS", "800")
)
ASR_CONTEXT_SENTENCES = int(os.getenv("ASR_CONTEXT_SENTENCES", "3"))
# 单条字幕/翻译上限：防止 interim/final 无限变长占内存与翻译额度。
ASR_MAX_SEGMENT_CHARS = int(os.getenv("ASR_MAX_SEGMENT_CHARS", "200"))
ASR_PREVIEW_TRANSLATE_CHARS = int(os.getenv("ASR_PREVIEW_TRANSLATE_CHARS", "80"))
ASR_FORCE_FINAL_MS = int(os.getenv("ASR_FORCE_FINAL_MS", "25000"))
ASR_HISTORY_DOM_LIMIT = int(os.getenv("ASR_HISTORY_DOM_LIMIT", "80"))
ASR_MERGE_MIN_CHARS = int(os.getenv("ASR_MERGE_MIN_CHARS", "40"))
ASR_MERGE_WAIT_MS = int(os.getenv("ASR_MERGE_WAIT_MS", "1800"))
# 阿里实时断句：课堂场景默认语义断句，减少「话说一半就被切开」。
ASR_ALIYUN_SEMANTIC_PUNCTUATION = os.getenv(
    "ASR_ALIYUN_SEMANTIC_PUNCTUATION", "true"
).strip().lower() in {"1", "true", "yes", "on"}
ASR_ALIYUN_MAX_SENTENCE_SILENCE_MS = int(
    os.getenv("ASR_ALIYUN_MAX_SENTENCE_SILENCE_MS", "1800")
)
# 长时间静音时保持连接：需持续推送静音 PCM（前端本就会推），并开启心跳。
ASR_ALIYUN_HEARTBEAT = os.getenv(
    "ASR_ALIYUN_HEARTBEAT", "true"
).strip().lower() in {"1", "true", "yes", "on"}

# ─── 企业翻译 API（可选）──────────────────────────────
# 如果要用付费翻译服务，在这里填写
ENTERPRISE_TRANSLATION_API_URL = os.getenv("ENTERPRISE_TRANSLATION_API_URL", "").strip()  # ← 翻译 API 地址
ENTERPRISE_TRANSLATION_API_KEY = os.getenv("ENTERPRISE_TRANSLATION_API_KEY", "").strip()  # ← 翻译 API Key
ASR_TIMEOUT_SECONDS = float(os.getenv("ASR_TIMEOUT_SECONDS", "20"))
ASR_MAX_SEGMENT_MB = int(os.getenv("ASR_MAX_SEGMENT_MB", "10"))
if ASR_TIMEOUT_SECONDS <= 0 or ASR_MAX_SEGMENT_MB <= 0:
    raise RuntimeError("ASR 超时和分片大小必须为正数")
if ASR_REALTIME_PREVIEW_INTERVAL_MS < 300 or not 0 <= ASR_CONTEXT_SENTENCES <= 5:
    raise RuntimeError("实时翻译间隔至少 300ms，上下文句数必须在 0 到 5 之间")
if min(ASR_MAX_SEGMENT_CHARS, ASR_PREVIEW_TRANSLATE_CHARS, ASR_FORCE_FINAL_MS, ASR_HISTORY_DOM_LIMIT) <= 0:
    raise RuntimeError("ASR 字幕切分/预览/强制断句/历史条数上限必须为正数")
if ASR_PREVIEW_TRANSLATE_CHARS > ASR_MAX_SEGMENT_CHARS:
    raise RuntimeError("ASR_PREVIEW_TRANSLATE_CHARS 不能大于 ASR_MAX_SEGMENT_CHARS")
if ASR_MERGE_MIN_CHARS <= 0 or ASR_MERGE_WAIT_MS <= 0:
    raise RuntimeError("ASR 短句合并阈值必须为正数")
if not 200 <= ASR_ALIYUN_MAX_SENTENCE_SILENCE_MS <= 6000:
    raise RuntimeError("ASR_ALIYUN_MAX_SENTENCE_SILENCE_MS 必须在 200～6000")
if IS_PRODUCTION and ASR_PROVIDER == "baidu" and not ASR_API_URL:
    raise RuntimeError("生产环境使用百度 ASR 时必须配置 ASR_API_URL")
if IS_PRODUCTION and ASR_PROVIDER == "aliyun" and not DASHSCOPE_API_KEY:
    raise RuntimeError("生产环境使用阿里 ASR 时必须配置 DASHSCOPE_API_KEY")
if ASR_PROVIDER == "aliyun" and not DASHSCOPE_API_KEY:
    import warnings
    warnings.warn("ASR_PROVIDER=aliyun 但未配置 DASHSCOPE_API_KEY，实时识别将不可用")

MAX_AVATAR_SIZE_MB = int(os.getenv("MAX_AVATAR_SIZE_MB", "2"))
MAX_AUDIO_SIZE_MB = int(os.getenv("MAX_AUDIO_SIZE_MB", "100"))

# ─── 课堂简报（可选 LLM；未配置时使用抽取式简报）────────
BRIEFING_LLM_API_URL = os.getenv("BRIEFING_LLM_API_URL", "").strip()
BRIEFING_LLM_API_KEY = os.getenv("BRIEFING_LLM_API_KEY", "").strip()
BRIEFING_LLM_MODEL = os.getenv("BRIEFING_LLM_MODEL", "deepseek-chat").strip() or "deepseek-chat"
BRIEFING_LLM_TIMEOUT_SECONDS = float(os.getenv("BRIEFING_LLM_TIMEOUT_SECONDS", "45"))
BRIEFING_MAX_SENTENCES = int(os.getenv("BRIEFING_MAX_SENTENCES", "400"))
BRIEFING_STALE_SECONDS = int(os.getenv("BRIEFING_STALE_SECONDS", "120"))
if BRIEFING_LLM_TIMEOUT_SECONDS <= 0 or BRIEFING_MAX_SENTENCES <= 0 or BRIEFING_STALE_SECONDS <= 0:
    raise RuntimeError("课堂简报超时、句数上限和过期时间必须为正数")
if BRIEFING_LLM_API_URL and not BRIEFING_LLM_API_KEY:
    import warnings
    warnings.warn("已配置 BRIEFING_LLM_API_URL 但未配置 BRIEFING_LLM_API_KEY，简报将使用抽取模式")

# ─── LLM Token 额度（滚动窗口，仅统计简报/助手大模型调用）──
LLM_QUOTA_WINDOW_DAYS = int(os.getenv("LLM_QUOTA_WINDOW_DAYS", "30"))
LLM_QUOTA_FREE_TOKENS = int(os.getenv("LLM_QUOTA_FREE_TOKENS", "200000"))
LLM_QUOTA_PREMIUM_TOKENS = int(os.getenv("LLM_QUOTA_PREMIUM_TOKENS", "2000000"))
if LLM_QUOTA_WINDOW_DAYS <= 0 or LLM_QUOTA_FREE_TOKENS < 0 or LLM_QUOTA_PREMIUM_TOKENS < 0:
    raise RuntimeError("LLM 额度窗口与默认上限必须为非负，且窗口天数 > 0")

-- ============================================================
-- LiveTrans Voice — 数据库建表脚本
-- 产品: 实时语音翻译 (课堂录音→ASR→翻译→收藏)
-- 数据库: MySQL 8.0+
-- 创建日期: 2026-06-28
-- ============================================================

CREATE DATABASE IF NOT EXISTS livetrans_voice
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;
USE livetrans_voice;

-- ============================================================
-- 1. 用户表
-- 前端: login.html / register.html / profile.html
-- ============================================================
CREATE TABLE users (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT '用户ID',
    nickname        VARCHAR(64)     NOT NULL                  COMMENT '昵称',
    username        VARCHAR(64)     DEFAULT NULL              COMMENT '登录用户名',
    avatar_url      VARCHAR(512)    DEFAULT NULL              COMMENT '头像URL',
    email           VARCHAR(128)    DEFAULT NULL              COMMENT '邮箱',
    email_verified  TINYINT(1)      NOT NULL DEFAULT 0        COMMENT '邮箱已验证',
    phone           VARCHAR(20)     DEFAULT NULL              COMMENT '手机号(国际格式)',
    phone_verified  TINYINT(1)      NOT NULL DEFAULT 0        COMMENT '手机已验证',
    password_hash   VARCHAR(256)    DEFAULT NULL              COMMENT 'bcrypt密码哈希(12轮)',
    status          ENUM('active','disabled','deleting','deleted') NOT NULL DEFAULT 'active',

    -- 第三方登录
    wechat_openid   VARCHAR(128)    DEFAULT NULL              COMMENT '微信OpenID',
    apple_user_id   VARCHAR(256)    DEFAULT NULL              COMMENT 'Apple User ID',
    google_openid   VARCHAR(128)    DEFAULT NULL              COMMENT 'Google OpenID',

    -- 会员
    member_level    ENUM('free','premium') NOT NULL DEFAULT 'free',
    role            ENUM('user','admin','super_admin') NOT NULL DEFAULT 'user',

    -- 学业信息 (profile.html 展示)
    university      VARCHAR(256)    DEFAULT NULL              COMMENT '学校',
    major           VARCHAR(256)    DEFAULT NULL              COMMENT '专业',
    focus_area      VARCHAR(256)    DEFAULT NULL              COMMENT '专注领域 (如: CS & AI)',

    last_login_at   DATETIME        DEFAULT NULL,
    last_login_ip   VARCHAR(45)     DEFAULT NULL,
    deleted_at      DATETIME        DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uk_username (username),
    UNIQUE KEY uk_phone (phone),
    UNIQUE KEY uk_email (email),
    UNIQUE KEY uk_wechat (wechat_openid),
    UNIQUE KEY uk_apple  (apple_user_id),
    UNIQUE KEY uk_google (google_openid),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';


-- ============================================================
-- 2. 验证码表
-- 前端: register.html (手机号+验证码注册)
-- ============================================================
CREATE TABLE verification_codes (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    target          VARCHAR(128)    NOT NULL                  COMMENT '手机号或邮箱',
    target_type     ENUM('phone','email') NOT NULL,
    code            CHAR(6)         NOT NULL,
    scene           ENUM('register','login','reset_password','bind','delete_account') NOT NULL DEFAULT 'register',
    ip_address      VARCHAR(45)     DEFAULT NULL,
    expires_at      DATETIME        NOT NULL,
    used            TINYINT(1)      NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_target_scene (target, scene, created_at),
    INDEX idx_ip_time (ip_address, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='验证码表';


-- ============================================================
-- 3. 用户令牌表
-- JWT Access Token 默认15分钟 + Refresh Token 默认30天（数据库仅保存SHA-256摘要）
-- ============================================================
CREATE TABLE user_tokens (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id         BIGINT UNSIGNED NOT NULL,
    access_token    VARCHAR(512)    NOT NULL,
    refresh_token   VARCHAR(512)    NOT NULL,
    device_info     VARCHAR(256)    DEFAULT NULL,
    device_id       VARCHAR(128)    DEFAULT NULL,
    ip_address      VARCHAR(45)     DEFAULT NULL,
    access_expires  DATETIME        NOT NULL,
    refresh_expires DATETIME        NOT NULL,
    revoked         TINYINT(1)      NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_user (user_id),
    INDEX idx_access_token (access_token(64)),
    INDEX idx_refresh (refresh_token(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户令牌表';


-- ============================================================
-- 4. 用户设置表
-- 前端: recorder.html (语言/引擎偏好) + 翻译设置
-- ============================================================
CREATE TABLE user_settings (
    user_id             BIGINT UNSIGNED NOT NULL,

    -- 翻译偏好
    default_source_lang CHAR(5)         DEFAULT 'auto'       COMMENT '默认源语言(auto=自动检测)',
    default_target_lang CHAR(5)         DEFAULT 'zh-CN'      COMMENT '默认目标语言',
    default_engine      VARCHAR(32)     DEFAULT 'default'    COMMENT '翻译引擎(default/deepl/glossary)',
    translation_mode    ENUM('online','offline','auto') DEFAULT 'auto',

    -- 显示设置
    font_size           ENUM('small','medium','large') DEFAULT 'medium',
    dark_mode           ENUM('system','light','dark') DEFAULT 'system',

    -- 录音设置
    flash_mode          ENUM('auto','on','off') DEFAULT 'auto',
    ocr_frequency       ENUM('high','medium','low') DEFAULT 'medium',

    -- 存储
    history_auto_clean  TINYINT(1)      NOT NULL DEFAULT 1,
    history_keep_count  INT             NOT NULL DEFAULT 500,

    -- 云同步
    cloud_sync_enabled  TINYINT(1)      NOT NULL DEFAULT 0,
    sync_history        TINYINT(1)      NOT NULL DEFAULT 1,
    sync_bookmarks      TINYINT(1)      NOT NULL DEFAULT 1,
    sync_settings       TINYINT(1)      NOT NULL DEFAULT 1,

    updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户设置表';


-- ============================================================
-- 5. 支持语言表
-- 前端: recorder.html 语言选择
-- ============================================================
CREATE TABLE languages (
    code            CHAR(5)         NOT NULL                  COMMENT 'ISO语言代码',
    name_native     VARCHAR(64)     NOT NULL                  COMMENT '本地名称',
    name_en         VARCHAR(64)     NOT NULL                  COMMENT '英文名称',
    flag_emoji      VARCHAR(8)      DEFAULT NULL              COMMENT '国旗emoji',
    region          VARCHAR(32)     DEFAULT NULL              COMMENT '区域(东亚/欧洲/东南亚/南亚/其他)',
    supports_offline TINYINT(1)     NOT NULL DEFAULT 0,
    offline_size_mb  INT            DEFAULT NULL,
    sort_order       INT            NOT NULL DEFAULT 0,
    is_active        TINYINT(1)     NOT NULL DEFAULT 1,

    PRIMARY KEY (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='支持语言表';


-- ============================================================
-- 6. 课堂讲座记录
-- 前端: history.html (课堂记录列表), review.html (课堂回顾)
-- ============================================================
CREATE TABLE lectures (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT '课堂ID',
    user_id         BIGINT UNSIGNED NOT NULL                  COMMENT '用户ID',

    -- 课程信息 (recorder.html 顶部展示)
    course_name     VARCHAR(256)    NOT NULL                  COMMENT '课程名 (如: 计算机科学 101)',
    source_lang     CHAR(5)         NOT NULL                  COMMENT '源语言 (如: de)',
    target_lang     CHAR(5)         NOT NULL                  COMMENT '目标语言 (如: zh-CN)',

    -- 录音信息
    duration_seconds INT            NOT NULL DEFAULT 0        COMMENT '录音总时长(秒)',
    sentence_count  INT             NOT NULL DEFAULT 0        COMMENT '总句子数',
    bookmark_count  INT             NOT NULL DEFAULT 0        COMMENT '收藏数',
    audio_url       VARCHAR(512)    DEFAULT NULL              COMMENT '录音文件URL',
    audio_size_bytes BIGINT         DEFAULT NULL              COMMENT '录音文件大小',

    -- 课堂上下文
    location_name   VARCHAR(256)    DEFAULT NULL              COMMENT '地点 (如: 大学礼堂)',
    room            VARCHAR(64)     DEFAULT NULL              COMMENT '教室号 (如: R.204)',
    subject_tags    JSON            DEFAULT NULL              COMMENT '学科标签 (如: ["经济学","宏观"])',

    -- 状态
    status          ENUM('recording','paused','completed','failed') NOT NULL DEFAULT 'completed',
    exported        TINYINT(1)      NOT NULL DEFAULT 0        COMMENT '是否已导出',

    lecture_date    DATE            NOT NULL                  COMMENT '上课日期',
    started_at      DATETIME        DEFAULT NULL              COMMENT '开始时间',
    ended_at        DATETIME        DEFAULT NULL              COMMENT '结束时间',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_user_date (user_id, lecture_date DESC),
    INDEX idx_user_status_date (user_id, status, lecture_date DESC),
    INDEX idx_user_course (user_id, course_name),
    INDEX idx_date (lecture_date),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (source_lang) REFERENCES languages(code),
    FOREIGN KEY (target_lang) REFERENCES languages(code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='课堂讲座记录';


-- ============================================================
-- 7. 转录句子
-- 前端: recorder.html (字幕流), review.html (完整回放)
-- 每个句子 = 1条教授说的话 + 翻译结果
-- ============================================================
CREATE TABLE transcriptions (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT '句子ID',
    lecture_id      BIGINT UNSIGNED NOT NULL                  COMMENT '所属课堂',
    user_id         BIGINT UNSIGNED NOT NULL                  COMMENT '用户ID(冗余,加速查询)',

    -- 原文
    source_text     TEXT            NOT NULL                  COMMENT 'ASR识别的原文',
    source_lang     CHAR(5)         NOT NULL                  COMMENT '原文语种',
    ocr_confidence  DECIMAL(4,2)    DEFAULT NULL              COMMENT 'ASR置信度(0.00~1.00)',

    -- 译文
    translated_text TEXT            NOT NULL                  COMMENT '翻译结果',
    target_lang     CHAR(5)         NOT NULL                  COMMENT '目标语种',
    engine          VARCHAR(32)     NOT NULL DEFAULT 'default' COMMENT '翻译引擎',
    mode            ENUM('online','offline') NOT NULL DEFAULT 'online',

    -- 时间戳
    sentence_order  INT             NOT NULL                  COMMENT '句子序号(从1开始)',
    start_offset_ms INT             NOT NULL DEFAULT 0        COMMENT '音频起始偏移(毫秒)',
    end_offset_ms   INT             DEFAULT NULL              COMMENT '音频结束偏移(毫秒)',
    recorded_at     DATETIME        NOT NULL                  COMMENT '识别时间',

    -- 收藏 (反范式, 加速 history 列表查询)
    is_bookmarked   TINYINT(1)      NOT NULL DEFAULT 0,

    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_lecture_order (lecture_id, sentence_order),
    UNIQUE KEY uk_lecture_sentence_order (lecture_id, sentence_order),
    INDEX idx_user_bookmarked (user_id, is_bookmarked),
    INDEX idx_lecture_bookmarked (lecture_id, is_bookmarked),
    FULLTEXT INDEX ft_search (source_text, translated_text),
    FOREIGN KEY (lecture_id) REFERENCES lectures(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='转录句子表';


-- ============================================================
-- 8. 知识卡片 (收藏)
-- 前端: knowledge-cards.html, recorder.html (★收藏按钮)
-- 标签: ⭐重要 / ❓疑问 / 🎯考点 / 📖定义
-- ============================================================
CREATE TABLE bookmarks (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id         BIGINT UNSIGNED NOT NULL,
    transcription_id BIGINT UNSIGNED NOT NULL                COMMENT '关联的转录句子',
    lecture_id      BIGINT UNSIGNED NOT NULL                  COMMENT '所属课堂(冗余,加速查询)',

    -- 标签类型
    tag             ENUM('important','question','exam','definition') NOT NULL COMMENT '⭐重要/❓疑问/🎯考点/📖定义',

    -- 用户备注
    note            TEXT            DEFAULT NULL              COMMENT '用户添加的笔记',

    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uk_user_transcription (user_id, transcription_id),
    INDEX idx_user_tag (user_id, tag),
    INDEX idx_user_time (user_id, created_at DESC),
    INDEX idx_lecture (lecture_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (transcription_id) REFERENCES transcriptions(id) ON DELETE CASCADE,
    FOREIGN KEY (lecture_id) REFERENCES lectures(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识卡片(收藏)表';


-- ============================================================
-- 9. 用户统计 (profile.html 展示)
-- ============================================================
CREATE TABLE user_stats (
    user_id                 BIGINT UNSIGNED NOT NULL,

    -- 本周数据 (前端 profile.html 统计卡片)
    weekly_record_seconds   INT             NOT NULL DEFAULT 0 COMMENT '本周录制时长(秒)',
    total_bookmark_count    INT             NOT NULL DEFAULT 0 COMMENT '总收藏知识点数',
    total_lecture_count     INT             NOT NULL DEFAULT 0 COMMENT '总课堂数',
    total_record_seconds    INT             NOT NULL DEFAULT 0 COMMENT '总录制时长(秒)',

    current_streak_days     INT             NOT NULL DEFAULT 0 COMMENT '连续学习天数',
    weekly_bookmark_count   INT             NOT NULL DEFAULT 0 COMMENT '本周收藏数',
    exam_mastery_improve    INT             NOT NULL DEFAULT 0 COMMENT '考点掌握度提升(%)',

    updated_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户统计表';


-- ============================================================
-- 10. 课程表 (profile.html「我的课程表」)
-- ============================================================
CREATE TABLE course_schedule (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id         BIGINT UNSIGNED NOT NULL,
    course_name     VARCHAR(256)    NOT NULL,
    source_lang     CHAR(5)         NOT NULL,
    target_lang     CHAR(5)         NOT NULL,
    day_of_week     TINYINT         NOT NULL                  COMMENT '星期几(1-7)',
    start_time      TIME            NOT NULL,
    end_time        TIME            NOT NULL,
    room            VARCHAR(64)     DEFAULT NULL,
    professor_name  VARCHAR(128)    DEFAULT NULL,
    is_active       TINYINT(1)      NOT NULL DEFAULT 1,

    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_user_day (user_id, day_of_week),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='课程表';


-- ============================================================
-- 11. 管理员审计日志
-- ============================================================
CREATE TABLE admin_audit_logs (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    admin_id    BIGINT UNSIGNED NOT NULL,
    admin_name  VARCHAR(64) DEFAULT NULL COMMENT '管理员昵称（冗余快照）',
    action      VARCHAR(64) NOT NULL COMMENT '操作类型: user.disable, lecture.delete 等',
    target_type VARCHAR(32) DEFAULT NULL COMMENT '目标类型: user, lecture',
    target_id   BIGINT UNSIGNED DEFAULT NULL COMMENT '目标记录 ID',
    detail      JSON DEFAULT NULL COMMENT '变更摘要',
    ip_address  VARCHAR(45) DEFAULT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_admin_action (admin_id, action),
    INDEX idx_created_at (created_at),
    CONSTRAINT fk_audit_admin FOREIGN KEY (admin_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='管理员操作审计日志';


-- ============================================================
-- 外键补充
-- ============================================================
ALTER TABLE user_tokens ADD CONSTRAINT fk_token_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

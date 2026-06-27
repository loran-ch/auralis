-- ============================================================
-- LiveTrans v1.01 — 数据库建表脚本
-- 依据: PRD v1.01 §4.7 用户账户系统 & §4.5 历史与收藏
-- 数据库: MySQL 8.0
-- 创建日期: 2026-06-28
-- ============================================================

CREATE DATABASE IF NOT EXISTS livetrans
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;
USE livetrans;

-- ============================================================
-- 1. 用户表 (PRD §4.7.2 注册方式, §4.7.8 用户状态)
-- ============================================================
CREATE TABLE users (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT '用户ID',
    nickname        VARCHAR(64)     DEFAULT NULL              COMMENT '昵称',
    avatar_url      VARCHAR(512)    DEFAULT NULL              COMMENT '头像URL',
    email           VARCHAR(128)    DEFAULT NULL              COMMENT '邮箱(邮箱注册/绑定)',
    email_verified  TINYINT(1)      NOT NULL DEFAULT 0        COMMENT '邮箱是否验证: 0否 1是',
    phone           VARCHAR(20)     DEFAULT NULL              COMMENT '手机号(国际格式)',
    phone_verified  TINYINT(1)      NOT NULL DEFAULT 0        COMMENT '手机号是否验证: 0否 1是',
    password_hash   VARCHAR(256)    DEFAULT NULL              COMMENT 'bcrypt密码哈希(邮箱注册时使用)',
    status          ENUM('active','disabled','deleting','deleted') NOT NULL DEFAULT 'active'
                    COMMENT '账户状态: active正常 disabled禁用 deleting注销冷静期 deleted已删除',
    deleted_at      DATETIME        DEFAULT NULL              COMMENT '注销申请时间(30天冷静期起点)',

    -- 第三方绑定
    wechat_openid   VARCHAR(128)    DEFAULT NULL              COMMENT '微信OpenID',
    apple_user_id   VARCHAR(256)    DEFAULT NULL              COMMENT 'Apple User ID',
    google_openid   VARCHAR(128)    DEFAULT NULL              COMMENT 'Google OpenID',

    -- 会员
    member_level    ENUM('free','pro') NOT NULL DEFAULT 'free' COMMENT '会员等级',
    member_since    DATE            DEFAULT NULL              COMMENT '专业会员起始日期',

    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    last_login_at   DATETIME        DEFAULT NULL              COMMENT '最后登录时间',
    last_login_ip   VARCHAR(45)     DEFAULT NULL              COMMENT '最后登录IP',

    PRIMARY KEY (id),
    UNIQUE KEY uk_phone (phone),
    UNIQUE KEY uk_email (email),
    UNIQUE KEY uk_wechat (wechat_openid),
    UNIQUE KEY uk_apple  (apple_user_id),
    UNIQUE KEY uk_google (google_openid),
    INDEX idx_status (status),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';


-- ============================================================
-- 2. 验证码表 (PRD §4.7.2 手机号+验证码注册)
-- ============================================================
CREATE TABLE verification_codes (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT 'ID',
    target          VARCHAR(128)    NOT NULL                  COMMENT '目标(手机号或邮箱)',
    target_type     ENUM('phone','email') NOT NULL            COMMENT '目标类型',
    code            CHAR(6)         NOT NULL                  COMMENT '6位验证码',
    scene           ENUM('register','login','reset_password','bind','unbind','delete_account')
                                    NOT NULL DEFAULT 'register' COMMENT '使用场景',
    ip_address      VARCHAR(45)     DEFAULT NULL              COMMENT '请求IP(用于频率限制)',
    expires_at      DATETIME        NOT NULL                  COMMENT '过期时间',
    used            TINYINT(1)      NOT NULL DEFAULT 0        COMMENT '是否已使用',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发送时间',

    PRIMARY KEY (id),
    INDEX idx_target_scene (target, scene, created_at),
    INDEX idx_ip (ip_address, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='验证码表';


-- ============================================================
-- 3. 用户令牌表 (PRD §4.7.3 Token管理)
-- ============================================================
CREATE TABLE user_tokens (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT 'ID',
    user_id         BIGINT UNSIGNED NOT NULL                  COMMENT '用户ID',
    access_token    VARCHAR(512)    NOT NULL                  COMMENT 'JWT Access Token',
    refresh_token   VARCHAR(512)    NOT NULL                  COMMENT 'Refresh Token',
    device_info     VARCHAR(256)    DEFAULT NULL              COMMENT '设备信息(型号/系统版本)',
    device_id       VARCHAR(128)    DEFAULT NULL              COMMENT '设备唯一标识',
    ip_address      VARCHAR(45)     DEFAULT NULL              COMMENT '登录IP',
    access_expires  DATETIME        NOT NULL                  COMMENT 'Access Token过期时间(7天)',
    refresh_expires DATETIME        NOT NULL                  COMMENT 'Refresh Token过期时间(30天)',
    revoked         TINYINT(1)      NOT NULL DEFAULT 0        COMMENT '是否已撤销',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_user (user_id),
    INDEX idx_refresh (refresh_token(255)),
    INDEX idx_device (user_id, device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户令牌表';


-- ============================================================
-- 4. 登录设备管理 (PRD §4.7.7 设备管理)
-- ============================================================
CREATE TABLE user_devices (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT 'ID',
    user_id         BIGINT UNSIGNED NOT NULL                  COMMENT '用户ID',
    device_id       VARCHAR(128)    NOT NULL                  COMMENT '设备唯一标识',
    device_name     VARCHAR(128)    DEFAULT NULL              COMMENT '设备名称(如 iPhone 15 Pro)',
    device_os       VARCHAR(64)     DEFAULT NULL              COMMENT '操作系统(iOS/Android)',
    os_version      VARCHAR(32)     DEFAULT NULL              COMMENT '系统版本',
    app_version     VARCHAR(16)     DEFAULT NULL              COMMENT 'App版本',
    last_active_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '最后活跃时间',
    is_trusted      TINYINT(1)      NOT NULL DEFAULT 1        COMMENT '是否受信任设备',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uk_user_device (user_id, device_id),
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户设备表';


-- ============================================================
-- 5. 支持语言表 (PRD §4.2.3 语言列表, §12.2 完整清单)
-- ============================================================
CREATE TABLE languages (
    code            CHAR(5)         NOT NULL                  COMMENT '语言代码(ISO 639-1, 如 zh-CN)',
    name_native     VARCHAR(64)     NOT NULL                  COMMENT '本地名称(如 简体中文)',
    name_en         VARCHAR(64)     NOT NULL                  COMMENT '英文名称(如 Simplified Chinese)',
    region          VARCHAR(32)     DEFAULT NULL              COMMENT '所属区域(东亚/欧洲/东南亚/南亚/其他)',
    flag_emoji      VARCHAR(8)      DEFAULT NULL              COMMENT '国旗emoji',
    supports_ocr    TINYINT(1)      NOT NULL DEFAULT 1        COMMENT '是否支持OCR识别',
    supports_offline TINYINT(1)     NOT NULL DEFAULT 0        COMMENT '是否支持离线翻译',
    offline_size_mb INT             DEFAULT NULL              COMMENT '离线包大小(MB)',
    sort_order      INT             NOT NULL DEFAULT 0        COMMENT '排序权重',
    is_active       TINYINT(1)      NOT NULL DEFAULT 1        COMMENT '是否启用',

    PRIMARY KEY (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='支持语言表';


-- ============================================================
-- 6. 翻译记录表 (PRD §4.5.1 翻译历史)
-- ============================================================
CREATE TABLE translation_records (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT '记录ID',
    user_id         BIGINT UNSIGNED DEFAULT NULL              COMMENT '用户ID(NULL=游客本地记录)',
    source_lang     CHAR(5)         NOT NULL                  COMMENT '源语言代码',
    target_lang     CHAR(5)         NOT NULL                  COMMENT '目标语言代码',
    source_text     TEXT            NOT NULL                  COMMENT '原始文本',
    translated_text TEXT            NOT NULL                  COMMENT '翻译后文本',
    ocr_confidence  DECIMAL(4,2)    DEFAULT NULL              COMMENT 'OCR置信度(0.00~1.00)',
    engine          VARCHAR(32)     NOT NULL DEFAULT 'default' COMMENT '翻译引擎(default/deepl/glossary)',
    mode            ENUM('online','offline') NOT NULL DEFAULT 'online' COMMENT '在线/离线模式',
    is_quick_capture TINYINT(1)     NOT NULL DEFAULT 0        COMMENT '是否拍照快译',
    image_url       VARCHAR(512)    DEFAULT NULL              COMMENT '原始图片URL(拍照快译时)',
    tags            JSON            DEFAULT NULL              COMMENT '自动识别标签(JSON数组)',

    -- 地理位置上下文
    latitude        DECIMAL(10,7)   DEFAULT NULL              COMMENT '翻译时纬度',
    longitude       DECIMAL(10,7)   DEFAULT NULL              COMMENT '翻译时经度',
    location_name   VARCHAR(256)    DEFAULT NULL              COMMENT '位置描述(如 柏林, 德国)',

    -- 元数据
    duration_ms     INT             DEFAULT NULL              COMMENT '翻译耗时(毫秒)',
    is_favorite     TINYINT(1)      NOT NULL DEFAULT 0        COMMENT '是否收藏: 0否 1是',
    is_deleted      TINYINT(1)      NOT NULL DEFAULT 0        COMMENT '软删除: 0否 1是',
    sync_status     ENUM('local','syncing','synced','conflict') NOT NULL DEFAULT 'local'
                    COMMENT '同步状态: local仅本地 syncing同步中 synced已同步 conflict冲突',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '翻译时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_user_time (user_id, created_at DESC),
    INDEX idx_user_favorite (user_id, is_favorite),
    INDEX idx_user_sync (user_id, sync_status),
    INDEX idx_lang_pair (source_lang, target_lang),
    INDEX idx_created (created_at),
    FULLTEXT INDEX ft_search (source_text, translated_text)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='翻译记录表';


-- ============================================================
-- 7. 用户设置表 (PRD §4.6 设置)
-- ============================================================
CREATE TABLE user_settings (
    user_id         BIGINT UNSIGNED NOT NULL                  COMMENT '用户ID',
    -- 翻译偏好
    default_source_lang  CHAR(5)     DEFAULT 'auto'           COMMENT '默认源语言(auto=自动检测)',
    default_target_lang  CHAR(5)     DEFAULT 'zh-CN'          COMMENT '默认目标语言',
    default_engine       VARCHAR(32) DEFAULT 'default'        COMMENT '默认翻译引擎',
    translation_mode     ENUM('online','offline','auto') DEFAULT 'auto'
                          COMMENT '翻译模式: online在线 offline离线 auto自动',

    -- 显示设置
    font_size        ENUM('small','medium','large') DEFAULT 'medium' COMMENT '译文字号',
    translation_position ENUM('below','overlay') DEFAULT 'below'  COMMENT '译文位置: below下方 overlay叠加',
    show_original     TINYINT(1)   NOT NULL DEFAULT 1        COMMENT '是否显示原文',
    dark_mode         ENUM('system','light','dark') DEFAULT 'system' COMMENT '深色模式',

    -- 取景器设置
    flash_mode        ENUM('auto','on','off') DEFAULT 'auto' COMMENT '闪光灯模式',
    ocr_frequency     ENUM('high','medium','low') DEFAULT 'medium'
                       COMMENT 'OCR检测频率: high 200ms medium 300ms low 500ms',

    -- 存储设置
    history_auto_clean   TINYINT(1) NOT NULL DEFAULT 1       COMMENT '是否自动清理历史',
    history_keep_count    INT        NOT NULL DEFAULT 500    COMMENT '保留记录数上限',

    -- 云同步
    cloud_sync_enabled    TINYINT(1) NOT NULL DEFAULT 0       COMMENT '是否开启云同步',
    sync_history         TINYINT(1)  NOT NULL DEFAULT 1       COMMENT '同步翻译历史',
    sync_favorites       TINYINT(1)  NOT NULL DEFAULT 1       COMMENT '同步收藏',
    sync_settings        TINYINT(1)  NOT NULL DEFAULT 1       COMMENT '同步应用设置',

    -- 隐私
    ocr_image_cache      TINYINT(1)  NOT NULL DEFAULT 1       COMMENT 'OCR图片缓存',
    share_analytics      TINYINT(1)  NOT NULL DEFAULT 1       COMMENT '分享使用数据',

    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户设置表';


-- ============================================================
-- 8. 离线语言包下载记录 (PRD §4.6 离线包)
-- ============================================================
CREATE TABLE offline_packs (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT 'ID',
    user_id         BIGINT UNSIGNED NOT NULL                  COMMENT '用户ID',
    lang_code       CHAR(5)         NOT NULL                  COMMENT '语言代码',
    pack_version    VARCHAR(16)     NOT NULL                  COMMENT '离线包版本',
    pack_size_mb    INT             NOT NULL                  COMMENT '包大小(MB)',
    download_status ENUM('downloading','paused','completed','failed') NOT NULL DEFAULT 'downloading'
                    COMMENT '下载状态',
    progress        DECIMAL(5,2)    DEFAULT 0.00              COMMENT '下载进度(0~100)',
    file_path       VARCHAR(512)    DEFAULT NULL              COMMENT '本地存储路径',
    downloaded_at   DATETIME        DEFAULT NULL              COMMENT '下载完成时间',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_user_lang (user_id, lang_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='离线语言包下载记录';


-- ============================================================
-- 9. 云同步日志 (PRD §4.7.6 云端同步)
-- ============================================================
CREATE TABLE sync_logs (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT 'ID',
    user_id         BIGINT UNSIGNED NOT NULL                  COMMENT '用户ID',
    device_id       VARCHAR(128)    DEFAULT NULL              COMMENT '设备标识',
    direction       ENUM('upload','download') NOT NULL        COMMENT '同步方向',
    data_type       ENUM('history','favorite','settings','profile','offline_pack') NOT NULL
                    COMMENT '同步数据类型',
    item_count      INT             NOT NULL DEFAULT 0        COMMENT '同步条目数',
    conflict_count  INT             NOT NULL DEFAULT 0        COMMENT '冲突条目数',
    duration_ms     INT             DEFAULT NULL              COMMENT '耗时(毫秒)',
    status          ENUM('success','partial','failed') NOT NULL COMMENT '同步结果',
    error_msg       TEXT            DEFAULT NULL              COMMENT '错误信息',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_user_time (user_id, created_at DESC),
    INDEX idx_user_type (user_id, data_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='云同步日志表';


-- ============================================================
-- 10. 用户操作日志 (PRD §9.3 埋点方案基础)
-- ============================================================
CREATE TABLE user_activity_logs (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT  COMMENT 'ID',
    user_id         BIGINT UNSIGNED DEFAULT NULL              COMMENT '用户ID(NULL为游客)',
    device_id       VARCHAR(128)    DEFAULT NULL              COMMENT '设备标识',
    event           VARCHAR(64)     NOT NULL                  COMMENT '事件名(如 session_start,ocr_detect,translate_request)',
    event_params    JSON            DEFAULT NULL              COMMENT '事件参数JSON',
    os_version      VARCHAR(32)     DEFAULT NULL              COMMENT '系统版本',
    app_version     VARCHAR(16)     DEFAULT NULL              COMMENT 'App版本',
    ip_address      VARCHAR(45)     DEFAULT NULL              COMMENT 'IP地址',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_user_event (user_id, event, created_at),
    INDEX idx_event_time (event, created_at),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户操作日志(埋点)';


-- ============================================================
-- 外键约束
-- ============================================================
ALTER TABLE user_tokens        ADD CONSTRAINT fk_token_user  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE user_devices       ADD CONSTRAINT fk_device_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE user_settings      ADD CONSTRAINT fk_setting_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE offline_packs      ADD CONSTRAINT fk_pack_user   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE sync_logs          ADD CONSTRAINT fk_sync_user   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE translation_records ADD CONSTRAINT fk_record_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE translation_records ADD CONSTRAINT fk_record_src  FOREIGN KEY (source_lang) REFERENCES languages(code);
ALTER TABLE translation_records ADD CONSTRAINT fk_record_tgt  FOREIGN KEY (target_lang) REFERENCES languages(code);

-- LiveTrans Voice — 前台功能说明（管理员可编辑）
-- 已有库执行本脚本即可。应用启动时也会自动建表并写入默认文案。

CREATE TABLE IF NOT EXISTS app_guides (
  id BIGINT NOT NULL AUTO_INCREMENT,
  slug VARCHAR(64) NOT NULL,
  title VARCHAR(128) NOT NULL,
  subtitle VARCHAR(512) DEFAULT NULL,
  items JSON DEFAULT NULL,
  footer_hint VARCHAR(256) DEFAULT NULL,
  updated_by_name VARCHAR(64) DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_app_guide_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

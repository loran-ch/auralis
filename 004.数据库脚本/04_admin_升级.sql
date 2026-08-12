-- LiveTrans Voice — 后台管理系统 数据库升级
-- 执行方式: mysql -u root -p livetrans_voice < 04_admin_升级.sql
-- 升级后请手动将初始管理员设为超级管理员（见文件末尾注释）

USE livetrans_voice;

-- 1. 用户新增角色字段（兼容重复执行）
SET @sql = IF(
  EXISTS(SELECT 1 FROM information_schema.columns
         WHERE table_schema = DATABASE() AND table_name = 'users'
           AND column_name = 'role'),
  'SELECT ''users.role already exists''',
  'ALTER TABLE users ADD COLUMN role ENUM(''user'',''admin'',''super_admin'') NOT NULL DEFAULT ''user'' AFTER member_level'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 2. 管理员操作审计日志表
CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    admin_id    BIGINT UNSIGNED NOT NULL,
    admin_name  VARCHAR(64) COMMENT '管理员昵称（冗余快照）',
    action      VARCHAR(64) NOT NULL COMMENT '操作类型: user.disable, lecture.delete 等',
    target_type VARCHAR(32) COMMENT '目标类型: user, lecture',
    target_id   BIGINT UNSIGNED COMMENT '目标记录 ID',
    detail      JSON COMMENT '变更摘要',
    ip_address  VARCHAR(45),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_admin_action (admin_id, action),
    INDEX idx_created_at (created_at),
    CONSTRAINT fk_audit_admin FOREIGN KEY (admin_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 已执行过旧脚本的数据库补齐管理员名称快照字段。
SET @sql = IF(
  EXISTS(SELECT 1 FROM information_schema.columns
         WHERE table_schema = DATABASE() AND table_name = 'admin_audit_logs'
           AND column_name = 'admin_name'),
  'SELECT ''admin_audit_logs.admin_name already exists''',
  'ALTER TABLE admin_audit_logs ADD COLUMN admin_name VARCHAR(64) NULL AFTER admin_id'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3. 将第一个注册用户设为超级管理员（请根据实际情况执行，id=1 为演示账号"学霸小李"）
-- UPDATE users SET role = 'super_admin' WHERE id = 1;
-- UPDATE users SET role = 'admin' WHERE id = 2;

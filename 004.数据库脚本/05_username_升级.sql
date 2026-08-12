-- LiveTrans Voice — 用户名字段升级（账号密码登录）
-- 执行方式: mysql -u root -p livetrans_voice < 05_username_升级.sql

USE livetrans_voice;

-- 新增 username 字段（唯一，允许 NULL 兼容旧用户，可重复执行）。
-- UNIQUE 约束本身已经提供登录查询所需索引，不再重复创建 idx_username。
SET @sql = IF(
  EXISTS(SELECT 1 FROM information_schema.columns
         WHERE table_schema = DATABASE() AND table_name = 'users'
           AND column_name = 'username'),
  'SELECT ''users.username already exists''',
  'ALTER TABLE users ADD COLUMN username VARCHAR(64) UNIQUE AFTER nickname'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

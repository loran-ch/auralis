-- LiveTrans Voice — 三语界面偏好（可重复执行）
-- 执行：mysql -u root -p livetrans_voice < 21_interface_locale_p0.sql
USE livetrans_voice;

SET @sql = IF(
  EXISTS(SELECT 1 FROM information_schema.columns
         WHERE table_schema = DATABASE() AND table_name = 'user_settings'
           AND column_name = 'interface_locale'),
  'SELECT ''interface_locale already exists''',
  'ALTER TABLE user_settings ADD COLUMN interface_locale VARCHAR(16) NOT NULL DEFAULT ''zh-Hans'' AFTER default_target_lang COMMENT ''界面语言(zh-Hans/zh-HK/en)'''
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

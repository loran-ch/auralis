-- LiveTrans Voice v1.3 数据库增量升级（可重复执行）
-- 适用于早期版本数据库；最新 01 建表脚本已包含这些索引。
USE livetrans_voice;

-- 防止同一课堂在并发转录时出现重复句子序号。
SET @sql = IF(
  EXISTS(SELECT 1 FROM information_schema.statistics
         WHERE table_schema = DATABASE() AND table_name = 'transcriptions'
           AND index_name = 'uk_lecture_sentence_order'),
  'SELECT ''uk_lecture_sentence_order already exists''',
  'ALTER TABLE transcriptions ADD UNIQUE KEY uk_lecture_sentence_order (lecture_id, sentence_order)'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 加速服务端会话校验和课堂状态列表查询。
SET @sql = IF(
  EXISTS(SELECT 1 FROM information_schema.statistics
         WHERE table_schema = DATABASE() AND table_name = 'user_tokens'
           AND index_name = 'idx_access_token'),
  'SELECT ''idx_access_token already exists''',
  'CREATE INDEX idx_access_token ON user_tokens (access_token(64))'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
  EXISTS(SELECT 1 FROM information_schema.statistics
         WHERE table_schema = DATABASE() AND table_name = 'lectures'
           AND index_name = 'idx_user_status_date'),
  'SELECT ''idx_user_status_date already exists''',
  'CREATE INDEX idx_user_status_date ON lectures (user_id, status, lecture_date DESC)'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

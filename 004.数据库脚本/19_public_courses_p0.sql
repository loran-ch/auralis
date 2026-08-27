-- LiveTrans Voice — 公开课程 P0
-- 管理员可将自己的课程设为公开，其他登录用户只读浏览。

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = 'courses'
    AND column_name = 'is_public'
);
SET @sql := IF(
  @col_exists = 0,
  'ALTER TABLE courses ADD COLUMN is_public TINYINT(1) NOT NULL DEFAULT 0 AFTER is_active',
  'SELECT ''courses.is_public already exists'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_exists := (
  SELECT COUNT(*) FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = 'courses'
    AND index_name = 'idx_course_public_active'
);
SET @sql := IF(
  @idx_exists = 0,
  'ALTER TABLE courses ADD KEY idx_course_public_active (is_public, is_active, updated_at)',
  'SELECT ''idx_course_public_active already exists'''
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

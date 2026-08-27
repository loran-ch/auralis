-- LiveTrans Voice — 课程中心 P0
-- 为已有库执行一次：新增课程系列、课堂课次与课表关联。

CREATE TABLE courses (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(256) NOT NULL,
  professor_name VARCHAR(128) NULL,
  room VARCHAR(64) NULL,
  term VARCHAR(64) NULL,
  source_lang VARCHAR(5) NOT NULL DEFAULT 'en',
  target_lang VARCHAR(5) NOT NULL DEFAULT 'zh-CN',
  translation_enabled TINYINT(1) NOT NULL DEFAULT 1,
  color VARCHAR(16) NOT NULL DEFAULT '#2563EB',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_course_user_active (user_id, is_active, updated_at),
  CONSTRAINT fk_courses_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE lectures
  ADD COLUMN course_id BIGINT UNSIGNED NULL AFTER user_id,
  ADD COLUMN session_number INT NULL AFTER course_id,
  ADD KEY idx_lecture_course_date (course_id, lecture_date),
  ADD UNIQUE KEY uk_course_session_number (course_id, session_number),
  ADD CONSTRAINT fk_lectures_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL;

ALTER TABLE course_schedule
  ADD COLUMN course_id BIGINT UNSIGNED NULL AFTER user_id,
  ADD KEY idx_schedule_course (course_id, day_of_week, start_time),
  ADD CONSTRAINT fk_schedule_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL;

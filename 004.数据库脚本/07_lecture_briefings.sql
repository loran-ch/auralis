-- LiveTrans Voice — 课堂简报
-- 已有库执行本脚本即可。新表按课堂一对一保存简报，删除课堂时级联删除。

CREATE TABLE IF NOT EXISTS lecture_briefings (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  lecture_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  status ENUM('generating', 'ready', 'failed', 'empty') NOT NULL DEFAULT 'generating',
  provider VARCHAR(64) DEFAULT NULL,
  overview TEXT,
  outline JSON,
  key_points JSON,
  exam_hints JSON,
  questions JSON,
  terms JSON,
  source_sentence_count INT NOT NULL DEFAULT 0,
  error_message VARCHAR(512) DEFAULT NULL,
  generated_at DATETIME DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_lecture_briefing (lecture_id),
  KEY idx_briefing_user (user_id),
  CONSTRAINT fk_briefing_lecture FOREIGN KEY (lecture_id) REFERENCES lectures (id) ON DELETE CASCADE,
  CONSTRAINT fk_briefing_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

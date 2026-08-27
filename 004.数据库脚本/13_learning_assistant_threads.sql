-- LiveTrans Voice — 独立学习助手会话与引用记录
-- 先执行 11_courses_p0.sql，再执行本脚本。

CREATE TABLE assistant_threads (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  course_id BIGINT UNSIGNED NULL,
  lecture_ids JSON NOT NULL,
  title VARCHAR(256) NOT NULL DEFAULT '新学习会话',
  summary TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_assistant_thread_user_updated (user_id, updated_at),
  KEY idx_assistant_thread_course (course_id, updated_at),
  CONSTRAINT fk_assistant_threads_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_assistant_threads_course FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE assistant_messages (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  thread_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  role ENUM('user', 'assistant') NOT NULL,
  content TEXT NOT NULL,
  citations JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_assistant_message_thread_created (thread_id, created_at, id),
  CONSTRAINT fk_assistant_messages_thread FOREIGN KEY (thread_id) REFERENCES assistant_threads(id) ON DELETE CASCADE,
  CONSTRAINT fk_assistant_messages_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

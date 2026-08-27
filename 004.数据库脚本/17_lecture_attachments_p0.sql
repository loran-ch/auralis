-- LiveTrans Voice — 课堂附件人工补录 P0
-- 用于作业截图、考点板书、通知 PDF、课件 PPT 等人工上传材料。

CREATE TABLE IF NOT EXISTS lecture_attachments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  lecture_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  category ENUM('assignment','exam','notice','other','material') NOT NULL DEFAULT 'other',
  title VARCHAR(256) NOT NULL,
  url VARCHAR(512) NOT NULL,
  content_type VARCHAR(128) NULL,
  size_bytes BIGINT NULL,
  status ENUM('ready','failed') NOT NULL DEFAULT 'ready',
  error_message VARCHAR(512) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_lecture_attachment_lecture (lecture_id, category, created_at),
  KEY idx_lecture_attachment_user (user_id, created_at),
  CONSTRAINT fk_lecture_attachments_lecture FOREIGN KEY (lecture_id) REFERENCES lectures (id) ON DELETE CASCADE,
  CONSTRAINT fk_lecture_attachments_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

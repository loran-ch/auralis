-- LiveTrans Voice — 可选课堂视频、关键帧与候选短片

CREATE TABLE media_assets (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  lecture_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  media_type ENUM('video','frame','clip') NOT NULL,
  status ENUM('uploaded','ready','processing','unavailable','failed') NOT NULL DEFAULT 'uploaded',
  url VARCHAR(512) NOT NULL,
  content_type VARCHAR(128) NULL,
  size_bytes BIGINT NULL,
  start_offset_ms INT NOT NULL DEFAULT 0,
  end_offset_ms INT NULL,
  metadata_json JSON NULL,
  error_message VARCHAR(512) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_media_asset_lecture_type (lecture_id, media_type, start_offset_ms),
  KEY idx_media_asset_user_created (user_id, created_at),
  CONSTRAINT fk_media_assets_lecture FOREIGN KEY (lecture_id) REFERENCES lectures(id) ON DELETE CASCADE,
  CONSTRAINT fk_media_assets_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE media_clip_candidates (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  lecture_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  title VARCHAR(256) NOT NULL,
  reason VARCHAR(512) NULL,
  start_offset_ms INT NOT NULL,
  end_offset_ms INT NOT NULL,
  score FLOAT NOT NULL DEFAULT 0,
  status ENUM('candidate','exporting','ready','unavailable','failed') NOT NULL DEFAULT 'candidate',
  media_url VARCHAR(512) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_clip_candidate_lecture (lecture_id, score),
  CONSTRAINT fk_clip_candidates_lecture FOREIGN KEY (lecture_id) REFERENCES lectures(id) ON DELETE CASCADE,
  CONSTRAINT fk_clip_candidates_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

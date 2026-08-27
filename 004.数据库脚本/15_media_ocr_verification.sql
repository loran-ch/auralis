-- LiveTrans Voice — OCR 与转录二次核验（原文不被覆盖）

CREATE TABLE transcription_verifications (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  lecture_id BIGINT UNSIGNED NOT NULL,
  transcription_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  status ENUM('processing','suggested','confirmed','unchanged','unavailable','failed') NOT NULL DEFAULT 'processing',
  original_text TEXT NOT NULL,
  suggested_text TEXT NULL,
  secondary_asr TEXT NULL,
  evidence_json JSON NULL,
  error_message VARCHAR(512) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_verification_transcription (transcription_id, created_at),
  KEY idx_verification_lecture (lecture_id, status),
  CONSTRAINT fk_verification_lecture FOREIGN KEY (lecture_id) REFERENCES lectures(id) ON DELETE CASCADE,
  CONSTRAINT fk_verification_transcription FOREIGN KEY (transcription_id) REFERENCES transcriptions(id) ON DELETE CASCADE,
  CONSTRAINT fk_verification_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE media_clip_candidates
  ADD COLUMN error_message VARCHAR(512) NULL AFTER media_url;

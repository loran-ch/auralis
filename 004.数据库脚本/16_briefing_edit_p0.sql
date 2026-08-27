-- LiveTrans Voice — 课堂简报人工修订 P0
-- 已有库执行一次。新库若已用更新后的 07_lecture_briefings.sql 建表可跳过。

ALTER TABLE lecture_briefings
  ADD COLUMN edit_status ENUM('auto', 'edited') NOT NULL DEFAULT 'auto' AFTER status;

ALTER TABLE lecture_briefings
  ADD COLUMN edited_at DATETIME NULL DEFAULT NULL AFTER generated_at;

ALTER TABLE lecture_briefings
  ADD COLUMN previous_payload JSON NULL AFTER error_message;

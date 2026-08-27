-- LiveTrans Voice — 课堂助手 P0 升级
-- 在已执行 07_lecture_briefings.sql 的数据库上执行一次。
-- assignments 保存从课堂转录中识别出的作业与通知；所有项目均须由用户确认。

ALTER TABLE lecture_briefings
  ADD COLUMN assignments JSON NULL AFTER terms;

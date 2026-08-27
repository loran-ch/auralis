-- LiveTrans Voice — 课堂标题
-- 已有数据库执行一次。课程名称与每一节课的显示标题分离，避免重命名破坏课程归类。

ALTER TABLE lectures
  ADD COLUMN title VARCHAR(256) NULL AFTER course_name;

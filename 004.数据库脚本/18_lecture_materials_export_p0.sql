-- LiveTrans Voice — 课件资料与导出 P0
-- 扩展 lecture_attachments.category，支持 PPT/课件等学习资料。

ALTER TABLE lecture_attachments
  MODIFY COLUMN category ENUM(
    'assignment',
    'exam',
    'notice',
    'other',
    'material'
  ) NOT NULL DEFAULT 'other';

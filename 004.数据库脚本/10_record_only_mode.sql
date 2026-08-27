-- LiveTrans Voice — 仅记录模式
-- 已有数据库执行一次。关闭翻译后，系统保存原始转录与音频时间轴，不调用翻译服务。

ALTER TABLE lectures
  ADD COLUMN translation_enabled TINYINT(1) NOT NULL DEFAULT 1 AFTER target_lang;

-- LiveTrans Voice — 生产环境基础数据（可重复执行）
-- 仅包含业务运行必需的语言配置，不创建演示用户或演示课堂。
USE livetrans_voice;

INSERT INTO languages
  (code, name_native, name_en, flag_emoji, region, supports_offline, offline_size_mb, sort_order)
VALUES
  ('zh-CN','简体中文','Simplified Chinese','🇨🇳','东亚',0,NULL,1),
  ('zh-TW','繁體中文','Traditional Chinese','🇹🇼','东亚',0,NULL,2),
  ('ja','日本語','Japanese','🇯🇵','东亚',1,62,3),
  ('ko','한국어','Korean','🇰🇷','东亚',1,55,4),
  ('en','English','English','🇬🇧','欧洲',1,48,10),
  ('de','Deutsch','German','🇩🇪','欧洲',1,58,11),
  ('fr','Français','French','🇫🇷','欧洲',1,52,12),
  ('es','Español','Spanish','🇪🇸','欧洲',1,50,13),
  ('pt','Português','Portuguese','🇵🇹','欧洲',1,54,14),
  ('it','Italiano','Italian','🇮🇹','欧洲',1,51,15),
  ('ru','Русский','Russian','🇷🇺','欧洲',1,65,16),
  ('th','ภาษาไทย','Thai','🇹🇭','东南亚',1,60,50),
  ('vi','Tiếng Việt','Vietnamese','🇻🇳','东南亚',0,NULL,51),
  ('ar','العربية','Arabic','🇸🇦','南亚',0,NULL,71),
  ('hi','हिन्दी','Hindi','🇮🇳','南亚',0,NULL,72),
  ('tr','Türkçe','Turkish','🇹🇷','南亚',0,NULL,73)
ON DUPLICATE KEY UPDATE
  name_native = VALUES(name_native),
  name_en = VALUES(name_en),
  flag_emoji = VALUES(flag_emoji),
  region = VALUES(region),
  supports_offline = VALUES(supports_offline),
  offline_size_mb = VALUES(offline_size_mb),
  sort_order = VALUES(sort_order);

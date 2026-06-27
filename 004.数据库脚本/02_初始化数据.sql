-- ============================================================
-- LiveTrans v1.01 — 初始化数据脚本
-- 依据: PRD §12.2 v1.0 完整语言支持清单
-- ============================================================

USE livetrans;

-- ============================================================
-- 1. 语言数据 (PRD §12.2 — 50种语言)
-- ============================================================
INSERT INTO languages (code, name_native, name_en, region, flag_emoji, supports_offline, offline_size_mb, sort_order) VALUES
-- 东亚
('zh-CN', '简体中文',   'Simplified Chinese',  '东亚',   '🇨🇳', 0, NULL, 1),
('zh-TW', '繁體中文',   'Traditional Chinese', '东亚',   '🇹🇼', 0, NULL, 2),
('ja',    '日本語',     'Japanese',            '东亚',   '🇯🇵', 1, 62,   3),
('ko',    '한국어',     'Korean',              '东亚',   '🇰🇷', 1, 55,   4),

-- 欧洲
('en',    'English',    'English',             '欧洲',   '🇬🇧', 1, 48,   10),
('fr',    'Français',   'French',              '欧洲',   '🇫🇷', 1, 52,   11),
('de',    'Deutsch',    'German',              '欧洲',   '🇩🇪', 1, 58,   12),
('es',    'Español',    'Spanish',             '欧洲',   '🇪🇸', 1, 50,   13),
('pt',    'Português',  'Portuguese',          '欧洲',   '🇵🇹', 1, 54,   14),
('it',    'Italiano',   'Italian',             '欧洲',   '🇮🇹', 1, 51,   15),
('ru',    'Русский',    'Russian',             '欧洲',   '🇷🇺', 1, 65,   16),
('nl',    'Nederlands', 'Dutch',               '欧洲',   '🇳🇱', 0, NULL, 17),
('pl',    'Polski',     'Polish',              '欧洲',   '🇵🇱', 0, NULL, 18),
('sv',    'Svenska',    'Swedish',             '欧洲',   '🇸🇪', 0, NULL, 19),
('da',    'Dansk',      'Danish',              '欧洲',   '🇩🇰', 0, NULL, 20),
('no',    'Norsk',      'Norwegian',           '欧洲',   '🇳🇴', 0, NULL, 21),
('fi',    'Suomi',      'Finnish',             '欧洲',   '🇫🇮', 0, NULL, 22),
('el',    'Ελληνικά',   'Greek',               '欧洲',   '🇬🇷', 0, NULL, 23),
('cs',    'Čeština',    'Czech',               '欧洲',   '🇨🇿', 0, NULL, 24),
('ro',    'Română',     'Romanian',            '欧洲',   '🇷🇴', 0, NULL, 25),
('hu',    'Magyar',     'Hungarian',           '欧洲',   '🇭🇺', 0, NULL, 26),
('uk',    'Українська', 'Ukrainian',           '欧洲',   '🇺🇦', 0, NULL, 27),
('ca',    'Català',     'Catalan',             '欧洲',   '🏴', 0, NULL, 28),
('hr',    'Hrvatski',   'Croatian',            '欧洲',   '🇭🇷', 0, NULL, 29),
('sk',    'Slovenčina', 'Slovak',              '欧洲',   '🇸🇰', 0, NULL, 30),
('bg',    'Български',  'Bulgarian',           '欧洲',   '🇧🇬', 0, NULL, 31),
('sl',    'Slovenščina','Slovenian',           '欧洲',   '🇸🇮', 0, NULL, 32),
('lt',    'Lietuvių',   'Lithuanian',          '欧洲',   '🇱🇹', 0, NULL, 33),
('lv',    'Latviešu',   'Latvian',             '欧洲',   '🇱🇻', 0, NULL, 34),
('et',    'Eesti',      'Estonian',            '欧洲',   '🇪🇪', 0, NULL, 35),
('is',    'Íslenska',   'Icelandic',           '欧洲',   '🇮🇸', 0, NULL, 36),
('ga',    'Gaeilge',    'Irish',               '欧洲',   '🇮🇪', 0, NULL, 37),
('cy',    'Cymraeg',    'Welsh',               '欧洲',   '🏴', 0, NULL, 38),

-- 东南亚
('th',    'ภาษาไทย',    'Thai',                '东南亚', '🇹🇭', 1, 60,   50),
('vi',    'Tiếng Việt', 'Vietnamese',          '东南亚', '🇻🇳', 0, NULL, 51),
('id',    'Bahasa Indonesia', 'Indonesian',    '东南亚', '🇮🇩', 0, NULL, 52),
('ms',    'Bahasa Melayu',    'Malay',         '东南亚', '🇲🇾', 0, NULL, 53),
('tl',    'Filipino',   'Filipino',            '东南亚', '🇵🇭', 0, NULL, 54),

-- 南亚/中东
('hi',    'हिन्दी',      'Hindi',               '南亚',   '🇮🇳', 0, NULL, 70),
('ar',    'العربية',    'Arabic',              '南亚',   '🇸🇦', 0, NULL, 71),
('he',    'עברית',      'Hebrew',              '南亚',   '🇮🇱', 0, NULL, 72),
('tr',    'Türkçe',     'Turkish',             '南亚',   '🇹🇷', 0, NULL, 73),
('ur',    'اردو',       'Urdu',                '南亚',   '🇵🇰', 0, NULL, 74),
('bn',    'বাংলা',       'Bengali',             '南亚',   '🇧🇩', 0, NULL, 75),
('ta',    'தமிழ்',       'Tamil',               '南亚',   '🇮🇳', 0, NULL, 76),
('te',    'తెలుగు',      'Telugu',              '南亚',   '🇮🇳', 0, NULL, 77),
('mr',    'मराठी',       'Marathi',             '南亚',   '🇮🇳', 0, NULL, 78),
('pa',    'ਪੰਜਾਬੀ',      'Punjabi',             '南亚',   '🇮🇳', 0, NULL, 79),

-- 其他
('af',    'Afrikaans',  'Afrikaans',           '其他',   '🇿🇦', 0, NULL, 99),
('sw',    'Kiswahili',  'Swahili',             '其他',   '🇰🇪', 0, NULL, 100);

-- ============================================================
-- 2. 测试用户 (开发用)
-- 密码: test123456 → bcrypt hash
-- ============================================================
INSERT INTO users (nickname, email, email_verified, phone, phone_verified, password_hash, member_level, member_since)
VALUES
('旅行者小王', 'demo@livetrans.app', 1, '+8613800000001', 1,
 '$2a$12$LJ3m4ys3Lk0TSwHCpNqr4OyGd6m0H8tQH5OqFOX0rRAZL9fVpFoPm',
 'pro', '2024-01-01'),
('留学生小李', 'student@livetrans.app', 1, '+8613800000002', 1,
 '$2a$12$LJ3m4ys3Lk0TSwHCpNqr4OyGd6m0H8tQH5OqFOX0rRAZL9fVpFoPm',
 'free', NULL),
('商务张总',   'biz@livetrans.app',    0, '+8613800000003', 1,
 '$2a$12$LJ3m4ys3Lk0TSwHCpNqr4OyGd6m0H8tQH5OqFOX0rRAZL9fVpFoPm',
 'pro', '2024-03-15');

-- ============================================================
-- 3. 测试用户设置
-- ============================================================
INSERT INTO user_settings (user_id, default_source_lang, default_target_lang, cloud_sync_enabled)
VALUES
(1, 'auto', 'zh-CN', 1),
(2, 'en',   'zh-CN', 1),
(3, 'de',   'zh-CN', 0);

-- ============================================================
-- 4. 测试翻译记录
-- ============================================================
INSERT INTO translation_records
  (user_id, source_lang, target_lang, source_text, translated_text, ocr_confidence, engine, mode, is_quick_capture, tags, location_name, duration_ms, is_favorite, sync_status, created_at)
VALUES
-- 用户1 的记录
(1, 'ja', 'zh-CN', '本日の特選：季節の鮮魚の握り盛り合わせ',
 '今日特选：季节鲜鱼握寿司拼盘', 0.95, 'default', 'online', 1,
 '["餐饮服务","日本料理","菜单识别"]', '东京, 日本', 320, 1, 'synced', '2026-06-27 14:20:00'),

(1, 'ja', 'zh-CN', '車両進入禁止。歩行者専用道路。',
 '车辆禁止进入。行人专用通道。', 0.88, 'default', 'online', 1,
 '["交通标识","道路标识"]', '东京, 日本', 280, 0, 'synced', '2026-06-27 10:05:00'),

-- 用户1 昨天的记录
(1, 'en', 'zh-CN', 'The collection features works from the late Edo period, showcasing the pinnacle of ukiyo-e craftsmanship.',
 '该藏品收录了江户晚期的作品，展示了浮世绘工艺的巅峰。', 0.92, 'default', 'online', 1,
 '["文化展览","艺术","博物馆"]', '柏林, 德国', 410, 1, 'synced', '2026-06-26 18:45:00'),

(1, 'fr', 'zh-CN', 'Mis en bouteille au château. Grand Vin de Bordeaux.',
 '酒庄装瓶。波尔多优质葡萄酒。', 0.90, 'deepl', 'online', 1,
 '["红酒","食品标签","法国"]', '巴黎, 法国', 350, 0, 'synced', '2026-06-26 12:30:00'),

-- 用户1 更早记录
(1, 'de', 'zh-CN', 'Wiener Schnitzel vom Kalb mit lauwarmem Kartoffel-Gurken-Salat und Preiselbeeren. Dazu ein Glas Riesling aus der Pfalz.',
 '维也纳小牛排配温热土豆黄瓜沙拉及蔓越莓酱。另附一杯来自普法尔茨地区的雷司令白葡萄酒。', 0.91, 'deepl', 'offline', 1,
 '["餐饮服务","德语文化","商务旅行","菜单识别"]', '柏林, 德国', 520, 0, 'synced', '2023-11-14 19:30:00'),

-- 用户2 的记录
(2, 'en', 'zh-CN', 'Please submit your assignment by Friday 5PM. Late submissions will not be accepted.',
 '请在周五下午5点前提交作业。逾期不予受理。', 0.96, 'default', 'online', 0,
 '["教育","校园"]', NULL, 290, 0, 'synced', '2026-06-27 09:00:00'),

-- 游客记录 (user_id=NULL)
(NULL, 'ja', 'zh-CN', 'ラーメン',
 '拉面', 0.98, 'default', 'online', 0,
 '["餐饮服务"]', NULL, 180, 0, 'local', '2026-06-27 15:00:00');

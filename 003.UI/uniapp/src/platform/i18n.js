import { computed, ref } from 'vue'

const LOCALE_KEY = 'livetrans-interface-locale'
export const SUPPORTED_LOCALES = ['zh-Hans', 'zh-HK', 'en']

const messages = {
  'zh-Hans': {
    'locale.simplified': '简体中文', 'locale.cantonese': '粤语（繁體）', 'locale.english': 'English',
    'nav.courses': '课程', 'nav.history': '记录', 'nav.recorder': '录音', 'nav.assistant': '助手', 'nav.profile': '我的',
    'common.save': '保存', 'common.cancel': '取消', 'common.edit': '编辑', 'common.add': '添加', 'common.loading': '加载中…',
    'common.user': '用户', 'common.autoDetect': '自动检测', 'common.none': '暂无', 'common.done': '完成',
    'profile.title': '个人中心', 'profile.subtitle': '账号、学习统计与偏好设置', 'profile.premium': '高级会员', 'profile.free': '免费账户',
    'profile.totalRecording': '总录音', 'profile.cards': '知识卡片', 'profile.records': '课堂记录', 'profile.preferences': '学习偏好',
    'profile.preferencesHint': '设置默认翻译语言和应用体验', 'profile.interfaceLanguage': '界面语言', 'profile.interfaceLanguageHint': '选择应用显示的语言',
    'profile.sourceLanguage': '原文语言', 'profile.sourceLanguageHint': '开始录音时自动选择', 'profile.targetLanguage': '翻译语言', 'profile.targetLanguageHint': '译文输出语言',
    'profile.translationMode': '翻译模式', 'profile.translationModeHint': '优先速度或离线可用性', 'profile.theme': '深色模式', 'profile.themeHint': '跟随系统或固定主题',
    'profile.cloud': '云端同步', 'profile.cloudHint': '同步历史、收藏与设置', 'profile.savePreferences': '保存偏好', 'profile.saving': '保存中…', 'profile.preferencesSaved': '偏好已保存',
    'profile.schedule': '课程表', 'profile.scheduleHint': '预先设置常用课堂和语言', 'profile.emptySchedule': '暂未添加课程',
    'profile.learning': '学习空间', 'profile.learningHint': '查看课程资料并向小橘子提问', 'profile.courseCenter': '课程中心', 'profile.courseCenterHint': '浏览我创建的课程和教师共享课程',
    'profile.classroomAssistant': '课堂助手', 'profile.classroomAssistantHint': '根据课堂记录、简报和作业进行复习', 'profile.security': '账号与安全',
    'profile.securityHint': '管理密码和登录设备', 'profile.changePassword': '修改密码', 'profile.changePasswordHint': '定期更换密码可提升安全性',
    'profile.logoutAll': '退出所有设备', 'profile.logoutAllHint': '撤销当前账号的全部登录会话', 'profile.logout': '退出当前账号',
    'recorder.title': '课堂录音', 'recorder.idle': '待机中', 'recorder.listening': '正在聆听…', 'recorder.recording': '实时录音', 'recorder.history': '课堂记录',
    'recorder.courseCenter': '课程中心', 'recorder.assistant': '课堂助手', 'recorder.cards': '知识卡片', 'recorder.profile': '个人中心', 'recorder.mark': '标记', 'recorder.bookmark': '收藏',
    'recorder.welcomeTitle': '让课堂内容实时变成双语笔记', 'recorder.welcomeCopy': '点击下方录音按钮开始。系统会自动断句、翻译并保存到课堂记录。',
    'recorder.confirmed': '已确认内容', 'recorder.sentences': '{count} 句', 'recorder.keepPrevious': '前文会持续保留', 'recorder.updating': '正在更新',
    'recorder.recognizing': '正在识别与理解上下文…', 'recorder.saveLecture': '保存课堂记录', 'recorder.later': '稍后再说', 'recorder.enterCourseName': '输入课程名称',
    'auth.welcomeBack': '欢迎回来', 'auth.account': '账号', 'auth.accountPlaceholder': '用户名或手机号码', 'auth.password': '登录密码', 'auth.passwordPlaceholder': '请输入密码',
    'auth.login': '登录', 'auth.loggingIn': '正在登录…', 'auth.noAccount': '还没有账号？', 'auth.registerNow': '立即注册', 'auth.forgot': '忘记密码？', 'auth.showPassword': '显示', 'auth.hidePassword': '隐藏', 'auth.thirdParty': '第三方登录', 'auth.agreement': '登录即代表您已阅读并同意《服务协议》与《隐私政策》', 'tag.important': '重要', 'tag.importantHint': '需要重点回顾', 'tag.question': '疑问', 'tag.questionHint': '课后需要查证', 'tag.exam': '考点', 'tag.examHint': '可能出现在考试中', 'tag.definition': '定义', 'tag.definitionHint': '概念与术语解释',
  },
  'zh-HK': {
    'locale.simplified': '簡體中文', 'locale.cantonese': '粵語（繁體）', 'locale.english': 'English',
    'nav.courses': '課程', 'nav.history': '紀錄', 'nav.recorder': '錄音', 'nav.assistant': '助手', 'nav.profile': '我嘅',
    'common.save': '儲存', 'common.cancel': '取消', 'common.edit': '編輯', 'common.add': '新增', 'common.loading': '載入中…',
    'common.user': '用戶', 'common.autoDetect': '自動偵測', 'common.none': '暫時冇', 'common.done': '完成',
    'profile.title': '個人中心', 'profile.subtitle': '帳戶、學習統計同偏好設定', 'profile.premium': '高級會員', 'profile.free': '免費帳戶',
    'profile.totalRecording': '總錄音', 'profile.cards': '知識卡', 'profile.records': '課堂紀錄', 'profile.preferences': '學習偏好',
    'profile.preferencesHint': '設定預設翻譯語言同應用體驗', 'profile.interfaceLanguage': '介面語言', 'profile.interfaceLanguageHint': '揀應用程式顯示嘅語言',
    'profile.sourceLanguage': '原文語言', 'profile.sourceLanguageHint': '開始錄音嗰陣自動揀', 'profile.targetLanguage': '翻譯語言', 'profile.targetLanguageHint': '譯文輸出語言',
    'profile.translationMode': '翻譯模式', 'profile.translationModeHint': '優先速度或者離線使用', 'profile.theme': '深色模式', 'profile.themeHint': '跟系統或者固定主題',
    'profile.cloud': '雲端同步', 'profile.cloudHint': '同步紀錄、收藏同設定', 'profile.savePreferences': '儲存偏好', 'profile.saving': '儲存中…', 'profile.preferencesSaved': '偏好已儲存',
    'profile.schedule': '課程表', 'profile.scheduleHint': '預先設定常用課堂同語言', 'profile.emptySchedule': '暫時未有課程',
    'profile.learning': '學習空間', 'profile.learningHint': '睇課程資料兼問小橘子', 'profile.courseCenter': '課程中心', 'profile.courseCenterHint': '瀏覽我建立嘅課程同老師分享嘅課程',
    'profile.classroomAssistant': '課堂助手', 'profile.classroomAssistantHint': '根據課堂紀錄、簡報同功課溫書', 'profile.security': '帳戶同安全',
    'profile.securityHint': '管理密碼同登入裝置', 'profile.changePassword': '更改密碼', 'profile.changePasswordHint': '定期換密碼可以提升安全性',
    'profile.logoutAll': '登出所有裝置', 'profile.logoutAllHint': '撤銷依家帳戶所有登入工作階段', 'profile.logout': '登出依家帳戶',
    'recorder.title': '課堂錄音', 'recorder.idle': '待機中', 'recorder.listening': '聽緊…', 'recorder.recording': '即時錄音', 'recorder.history': '課堂紀錄',
    'recorder.courseCenter': '課程中心', 'recorder.assistant': '課堂助手', 'recorder.cards': '知識卡', 'recorder.profile': '個人中心', 'recorder.mark': '標記', 'recorder.bookmark': '收藏',
    'recorder.welcomeTitle': '即時將課堂內容變做雙語筆記', 'recorder.welcomeCopy': '撳下面嘅錄音掣開始。系統會自動斷句、翻譯同儲存到課堂紀錄。',
    'recorder.confirmed': '已確認內容', 'recorder.sentences': '{count} 句', 'recorder.keepPrevious': '之前嘅內容會保留', 'recorder.updating': '更新緊',
    'recorder.recognizing': '辨識同理解緊上下文…', 'recorder.saveLecture': '儲存課堂紀錄', 'recorder.later': '遲啲先', 'recorder.enterCourseName': '輸入課程名稱',
    'auth.welcomeBack': '歡迎返嚟', 'auth.account': '帳戶', 'auth.accountPlaceholder': '用戶名稱或者手機號碼', 'auth.password': '登入密碼', 'auth.passwordPlaceholder': '請輸入密碼',
    'auth.login': '登入', 'auth.loggingIn': '登入緊…', 'auth.noAccount': '未有帳戶？', 'auth.registerNow': '立即註冊', 'auth.forgot': '唔記得密碼？', 'auth.showPassword': '顯示', 'auth.hidePassword': '隱藏', 'auth.thirdParty': '第三方登入', 'auth.agreement': '登入即代表你已閱讀並同意《服務協議》同《私隱政策》', 'tag.important': '重要', 'tag.importantHint': '要重點溫習', 'tag.question': '疑問', 'tag.questionHint': '下堂要查證', 'tag.exam': '考點', 'tag.examHint': '可能會喺考試出現', 'tag.definition': '定義', 'tag.definitionHint': '概念同術語解釋',
  },
  en: {
    'locale.simplified': '简体中文', 'locale.cantonese': 'Cantonese (繁體)', 'locale.english': 'English',
    'nav.courses': 'Courses', 'nav.history': 'History', 'nav.recorder': 'Record', 'nav.assistant': 'Assistant', 'nav.profile': 'Profile',
    'common.save': 'Save', 'common.cancel': 'Cancel', 'common.edit': 'Edit', 'common.add': 'Add', 'common.loading': 'Loading…',
    'common.user': 'User', 'common.autoDetect': 'Auto-detect', 'common.none': 'None', 'common.done': 'Done',
    'profile.title': 'Profile', 'profile.subtitle': 'Account, learning statistics and preferences', 'profile.premium': 'Premium', 'profile.free': 'Free account',
    'profile.totalRecording': 'Recording', 'profile.cards': 'Knowledge cards', 'profile.records': 'Lectures', 'profile.preferences': 'Learning preferences',
    'profile.preferencesHint': 'Set default translation and app preferences', 'profile.interfaceLanguage': 'Interface language', 'profile.interfaceLanguageHint': 'Choose the language shown in the app',
    'profile.sourceLanguage': 'Source language', 'profile.sourceLanguageHint': 'Selected when recording starts', 'profile.targetLanguage': 'Translation language', 'profile.targetLanguageHint': 'Language used for translated text',
    'profile.translationMode': 'Translation mode', 'profile.translationModeHint': 'Prioritize speed or offline availability', 'profile.theme': 'Dark mode', 'profile.themeHint': 'Follow system or choose a theme',
    'profile.cloud': 'Cloud sync', 'profile.cloudHint': 'Sync history, bookmarks and settings', 'profile.savePreferences': 'Save preferences', 'profile.saving': 'Saving…', 'profile.preferencesSaved': 'Preferences saved',
    'profile.schedule': 'Schedule', 'profile.scheduleHint': 'Set up frequently used lectures and languages', 'profile.emptySchedule': 'No classes yet',
    'profile.learning': 'Learning space', 'profile.learningHint': 'Browse course materials and ask Orange', 'profile.courseCenter': 'Course centre', 'profile.courseCenterHint': 'Browse courses you created and shared courses',
    'profile.classroomAssistant': 'Classroom assistant', 'profile.classroomAssistantHint': 'Review with lecture records, briefings and assignments', 'profile.security': 'Account & security',
    'profile.securityHint': 'Manage password and signed-in devices', 'profile.changePassword': 'Change password', 'profile.changePasswordHint': 'Changing passwords regularly improves security',
    'profile.logoutAll': 'Sign out of all devices', 'profile.logoutAllHint': 'Revoke every active session for this account', 'profile.logout': 'Sign out',
    'recorder.title': 'Lecture recording', 'recorder.idle': 'Ready', 'recorder.listening': 'Listening…', 'recorder.recording': 'Live recording', 'recorder.history': 'Lecture history',
    'recorder.courseCenter': 'Course centre', 'recorder.assistant': 'Classroom assistant', 'recorder.cards': 'Knowledge cards', 'recorder.profile': 'Profile', 'recorder.mark': 'Mark', 'recorder.bookmark': 'Bookmark',
    'recorder.welcomeTitle': 'Turn lectures into bilingual notes in real time', 'recorder.welcomeCopy': 'Tap the record button below to begin. Sentences are segmented, translated and saved automatically.',
    'recorder.confirmed': 'Confirmed', 'recorder.sentences': '{count} sentences', 'recorder.keepPrevious': 'Earlier content remains available', 'recorder.updating': 'Updating',
    'recorder.recognizing': 'Recognising speech and context…', 'recorder.saveLecture': 'Save lecture', 'recorder.later': 'Later', 'recorder.enterCourseName': 'Enter a course name',
    'auth.welcomeBack': 'Welcome back', 'auth.account': 'Account', 'auth.accountPlaceholder': 'Username or phone number', 'auth.password': 'Password', 'auth.passwordPlaceholder': 'Enter password',
    'auth.login': 'Sign in', 'auth.loggingIn': 'Signing in…', 'auth.noAccount': 'No account yet?', 'auth.registerNow': 'Create one', 'auth.forgot': 'Forgot password?', 'auth.showPassword': 'Show', 'auth.hidePassword': 'Hide', 'auth.thirdParty': 'Or continue with', 'auth.agreement': 'By signing in, you agree to the Terms of Service and Privacy Policy.', 'tag.important': 'Important', 'tag.importantHint': 'Review this carefully', 'tag.question': 'Question', 'tag.questionHint': 'Check after class', 'tag.exam': 'Exam point', 'tag.examHint': 'May appear in an exam', 'tag.definition': 'Definition', 'tag.definitionHint': 'A concept or term explanation',
  },
}

function preferredLocale() {
  const saved = uni.getStorageSync(LOCALE_KEY)
  if (SUPPORTED_LOCALES.includes(saved)) return saved
  try {
    const language = String(uni.getSystemInfoSync().language || '').toLowerCase()
    if (language.startsWith('en')) return 'en'
    if (language.includes('hk') || language.includes('yue')) return 'zh-HK'
  } catch (_) {}
  return 'zh-Hans'
}

const activeLocale = ref(preferredLocale())

export function t(key, params = {}) {
  const template = messages[activeLocale.value]?.[key] ?? messages['zh-Hans'][key] ?? key
  return template.replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? ''))
}

export function setLocale(value) {
  activeLocale.value = SUPPORTED_LOCALES.includes(value) ? value : preferredLocale()
  uni.setStorageSync(LOCALE_KEY, activeLocale.value)
  // #ifdef H5
  if (typeof document !== 'undefined') document.documentElement.lang = activeLocale.value
  // #endif
}

export function useLocale() { return computed(() => activeLocale.value) }

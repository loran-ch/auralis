export const tagMeta = {
  important: { label: '重要', icon: '⭐', color: '#874e00' },
  question: { label: '疑问', icon: '❓', color: '#8b5cf6' },
  exam: { label: '考点', icon: '🎯', color: '#ba1a1a' },
  definition: { label: '定义', icon: '📘', color: '#005ea1' },
}

export function formatDuration(seconds = 0) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  if (hours) return `${hours}小时${minutes}分钟`
  if (minutes) return `${minutes}分钟${secs ? `${secs}秒` : ''}`
  return `${secs}秒`
}

export function formatClock(seconds = 0) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0))
  const minutes = Math.floor(total / 60)
  const secs = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

export function formatDate(value, withTime = false) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const text = `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()}`
  return withTime ? `${text} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}` : text
}

export function languageLabel(code, languages = []) {
  const language = languages.find((item) => item.code === code)
  return language ? `${language.flag_emoji || '🌐'} ${language.name_native}` : code
}

export function showError(error, fallback = '操作失败') {
  uni.showToast({ title: error?.message || fallback, icon: 'none', duration: 2600 })
}

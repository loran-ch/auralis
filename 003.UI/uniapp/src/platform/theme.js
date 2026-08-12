import { computed, ref } from 'vue'

const THEME_KEY = 'livetrans-theme'
const mode = ref(uni.getStorageSync(THEME_KEY) || 'system')
const systemDark = ref(false)
let initialized = false

function initialize() {
  if (initialized) return
  initialized = true
  try { systemDark.value = uni.getSystemInfoSync().theme === 'dark' } catch (_) {}
  if (typeof uni.onThemeChange === 'function') {
    uni.onThemeChange((result) => { systemDark.value = result.theme === 'dark' })
  }
}

export function useTheme() {
  initialize()
  return computed(() => (mode.value === 'dark' || (mode.value === 'system' && systemDark.value)) ? 'theme-dark' : '')
}

export function setThemeMode(value) {
  mode.value = ['system', 'light', 'dark'].includes(value) ? value : 'system'
  uni.setStorageSync(THEME_KEY, mode.value)
}

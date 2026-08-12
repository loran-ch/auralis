const ACCESS_KEY = 'livetrans_token'
const REFRESH_KEY = 'livetrans_refresh_token'
const USER_KEY = 'livetrans_user'

export function getAccessToken() {
  return uni.getStorageSync(ACCESS_KEY) || ''
}

export function getRefreshToken() {
  return uni.getStorageSync(REFRESH_KEY) || ''
}

export function getStoredUser() {
  return uni.getStorageSync(USER_KEY) || null
}

export function saveAuth(payload) {
  if (!payload?.tokens?.access_token) throw new Error('登录响应格式异常')
  uni.setStorageSync(ACCESS_KEY, payload.tokens.access_token)
  uni.setStorageSync(REFRESH_KEY, payload.tokens.refresh_token || '')
  if (payload.user) uni.setStorageSync(USER_KEY, payload.user)
}

export function updateStoredUser(user) {
  if (user) uni.setStorageSync(USER_KEY, user)
}

export function clearAuth() {
  uni.removeStorageSync(ACCESS_KEY)
  uni.removeStorageSync(REFRESH_KEY)
  uni.removeStorageSync(USER_KEY)
}

export function requireAuth() {
  if (getAccessToken() || getRefreshToken()) return true
  uni.reLaunch({ url: '/pages/login/index' })
  return false
}

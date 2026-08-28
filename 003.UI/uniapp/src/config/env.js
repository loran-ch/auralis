const rawBaseUrl = import.meta.env.VITE_API_BASE_URL
  || (import.meta.env.DEV ? 'http://127.0.0.1:8002' : '')

function resolveApiBaseUrl(value) {
  let resolved = value

  // #ifdef H5
  // H5 开发环境统一走 Vite 同源代理。手机/模拟器无需访问自身的
  // 127.0.0.1，也不会触发 CORS 或 HTTPS 页面的混合内容限制。
  if (import.meta.env.DEV && typeof window !== 'undefined') {
    try {
      const url = new URL(value, window.location.origin)
      if (['127.0.0.1', 'localhost', '::1'].includes(url.hostname)) resolved = ''
    } catch (_) {}
  }
  // #endif

  return resolved.replace(/\/$/, '')
}

export const API_BASE_URL = resolveApiBaseUrl(rawBaseUrl)
export const APP_NAME = 'Auralis 智听'
export const REQUEST_TIMEOUT = 15000
export const ENABLE_DEMO_MODE = String(
  import.meta.env.VITE_ENABLE_DEMO_MODE ?? (import.meta.env.DEV ? 'true' : 'false'),
).toLowerCase() === 'true'

export function websocketApiUrl(path) {
  // #ifdef H5
  const base = API_BASE_URL || (typeof window !== 'undefined' ? window.location.origin : '')
  if (!base) return ''
  const url = new URL(path, `${base.replace(/\/$/, '')}/`)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
  // #endif
  // #ifndef H5
  return ''
  // #endif
}

export function absoluteAssetUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//i.test(path)) return path
  return `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`
}

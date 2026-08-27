import { API_BASE_URL, REQUEST_TIMEOUT } from '../config/env'
import {
  clearAuth,
  getAccessToken,
  getRefreshToken,
  saveAuth,
} from './session'

let refreshPromise = null

function errorMessage(data, fallback = '请求失败') {
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) {
    return data.detail.map((item) => item.msg || String(item)).join('；')
  }
  return data.message || fallback
}

function rawRequest(path, options = {}) {
  const header = { ...(options.header || {}) }
  if (options.auth !== false) {
    const token = getAccessToken()
    if (token) header.Authorization = `Bearer ${token}`
  }
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE_URL}${path}`,
      method: (options.method || 'GET').toUpperCase(),
      data: options.data,
      header,
      timeout: options.timeout || REQUEST_TIMEOUT,
      success: (response) => resolve(response),
      fail: (error) => reject(new Error(error.errMsg || '网络连接失败')),
    })
  })
}

async function refreshSession() {
  if (refreshPromise) return refreshPromise
  const refreshToken = getRefreshToken()
  if (!refreshToken) return null
  refreshPromise = rawRequest('/api/auth/refresh', {
    method: 'POST',
    auth: false,
    data: { refresh_token: refreshToken },
  }).then((response) => {
    if (response.statusCode < 200 || response.statusCode >= 300) return null
    saveAuth(response.data)
    return response.data.tokens.access_token
  }).catch(() => null).finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

export async function request(path, options = {}) {
  let response = await rawRequest(path, options)
  if (response.statusCode === 401 && options.auth !== false && options.retry !== false) {
    const token = await refreshSession()
    if (token) response = await rawRequest(path, { ...options, retry: false })
    else clearAuth()
  }
  if (response.statusCode < 200 || response.statusCode >= 300) {
    const error = new Error(errorMessage(response.data, `请求失败（${response.statusCode}）`))
    error.statusCode = response.statusCode
    error.data = response.data
    throw error
  }
  return response.data
}

function rawUpload(path, filePath, formData = {}) {
  const token = getAccessToken()
  return new Promise((resolve, reject) => {
    const uploadOptions = {
      url: `${API_BASE_URL}${path}`,
      name: 'file',
      formData,
      header: token ? { Authorization: `Bearer ${token}` } : {},
      timeout: 120000,
      success: (response) => {
        let data = response.data
        try { data = JSON.parse(response.data) } catch (_) {}
        resolve({ ...response, data })
      },
      fail: (error) => {
        const message = error?.errMsg || '文件上传失败'
        reject(new Error(
          /uploadFile:fail file error/i.test(message)
            ? '录音临时文件已失效，请结束后重新开始录音'
            : message,
        ))
      },
    }
    // #ifdef H5
    if (filePath instanceof Blob) {
      const blobUrl = URL.createObjectURL(filePath)
      uploadOptions.filePath = blobUrl
      const cleanup = () => { try { URL.revokeObjectURL(blobUrl) } catch (_) {} }
      const _origSuccess = uploadOptions.success
      const _origFail = uploadOptions.fail
      uploadOptions.success = (res) => { cleanup(); _origSuccess(res) }
      uploadOptions.fail = (err) => { cleanup(); _origFail(err) }
    } else {
      uploadOptions.filePath = filePath
    }
    // #endif
    // #ifndef H5
    if (typeof filePath !== 'string' || !filePath.trim()) {
      reject(new Error('录音文件路径无效'))
      return
    }
    uploadOptions.filePath = filePath
    // #endif
    uni.uploadFile(uploadOptions)
  })
}

export async function upload(path, filePath, formData = {}, retry = true) {
  let response = await rawUpload(path, filePath, formData)
  if (Number(response.statusCode) === 401 && retry) {
    const token = await refreshSession()
    if (token) response = await rawUpload(path, filePath, formData)
  }
  if (Number(response.statusCode) < 200 || Number(response.statusCode) >= 300) {
    const error = new Error(errorMessage(response.data, '文件上传失败'))
    error.statusCode = Number(response.statusCode)
    error.data = response.data
    throw error
  }
  return response.data
}

export async function streamAssistantAnswer(threadId, payload, handlers = {}) {
  const path = `/api/assistant/threads/${threadId}/ask/stream`
  // #ifdef H5
  const token = getAccessToken()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok || !response.body) {
    const error = new Error(`课堂助手请求失败（${response.status}）`)
    error.statusCode = response.status
    throw error
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const packets = buffer.split(/\r?\n\r?\n/)
    buffer = packets.pop() || ''
    packets.forEach((packet) => {
      const event = (packet.match(/^event:\s*(.+)$/m) || [])[1]
      const raw = (packet.match(/^data:\s*(.+)$/m) || [])[1]
      if (!event || !raw) return
      try { handlers[event]?.(JSON.parse(raw)) } catch (_) {}
    })
    if (done) break
  }
  return true
  // #endif

  // #ifndef H5
  // 原生 App / 小程序暂不支持 fetch ReadableStream，使用同一业务接口的完整响应降级，
  // 仍能得到工具化、可引用的回答，避免平台差异造成页面不可用。
  const result = await request(`/api/assistant/threads/${threadId}/ask`, {
    method: 'POST', data: payload, timeout: 60000,
  })
  handlers.delta?.({ content: result.answer || '' })
  handlers.done?.(result)
  return true
  // #endif
}

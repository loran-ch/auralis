import { getAccessToken } from '../api/session'
import { websocketApiUrl } from '../config/env'
import { startPcmCapture, stopPcmCapture } from './recorder'

let socket = null
let handlers = {}
let ready = false
let closing = false
let pendingFrames = []
let startPromise = null
let startResolver = null
let startRejecter = null
let startTimer = null
const MAX_BUFFERED_FRAMES = 32

export function isRealtimeSpeechSupported() {
  // #ifdef H5
  return typeof WebSocket !== 'undefined'
    && typeof window !== 'undefined'
    && Boolean(window.AudioContext || window.webkitAudioContext)
  // #endif
  // #ifndef H5
  return false
  // #endif
}

function settleStart(value, error = null) {
  if (!startResolver && !startRejecter) return
  const resolve = startResolver
  const reject = startRejecter
  startResolver = null
  startRejecter = null
  clearTimeout(startTimer)
  startTimer = null
  if (error) reject?.(error)
  else resolve?.(value)
}

function cleanup() {
  stopPcmCapture()
  pendingFrames = []
  ready = false
  socket = null
  startPromise = null
  clearTimeout(startTimer)
  startTimer = null
}

function handleMessage(event) {
  let message
  try { message = JSON.parse(event.data) } catch (_) { return }
  if (message.type === 'ready') {
    ready = true
    for (const frame of pendingFrames.splice(0)) {
      if (socket?.readyState === WebSocket.OPEN) socket.send(frame)
    }
    handlers.onReady?.(message)
    settleStart(true)
  } else if (message.type === 'interim') handlers.onInterim?.(message)
  else if (message.type === 'preview') handlers.onPreview?.(message)
  else if (message.type === 'finalizing') handlers.onFinalizing?.(message)
  else if (message.type === 'final') handlers.onFinal?.(message)
  else if (message.type === 'no_speech') handlers.onNoSpeech?.(message)
  else if (message.type === 'unsupported') {
    handlers.onFallback?.(message)
    settleStart(false)
  } else if (message.type === 'error') {
    handlers.onError?.(message)
    if (message.fallback) handlers.onFallback?.(message)
    if (!ready) settleStart(false)
  }
}

function sendPcmFrame(frame) {
  if (ready && socket?.readyState === WebSocket.OPEN) {
    socket.send(frame)
    return
  }
  pendingFrames.push(frame)
  if (pendingFrames.length > MAX_BUFFERED_FRAMES) pendingFrames.shift()
}

export function startRealtimeSpeech(lectureId, callbacks = {}, options = {}) {
  // #ifdef H5
  if (!isRealtimeSpeechSupported() || !lectureId) return Promise.resolve(false)
  if (startPromise) return startPromise
  const url = websocketApiUrl(`/api/lectures/${lectureId}/stream`)
  if (!url) return Promise.resolve(false)
  handlers = callbacks
  closing = false
  ready = false
  pendingFrames = []
  startPromise = new Promise((resolve, reject) => {
    startResolver = resolve
    startRejecter = reject
  })
  const pendingStart = startPromise
  startTimer = setTimeout(() => {
    handlers.onFallback?.({ message: '实时识别连接超时，已切换分片识别' })
    settleStart(false)
    try { socket?.close() } catch (_) {}
  }, 12000)
  try {
    socket = new WebSocket(url)
    socket.binaryType = 'arraybuffer'
    socket.onopen = async () => {
      socket.send(JSON.stringify({
        type: 'auth',
        token: getAccessToken(),
        offset_ms: Math.max(0, Number(options.offsetMs || 0)),
      }))
      try {
        const started = await startPcmCapture(sendPcmFrame)
        if (!started) {
          handlers.onFallback?.({ message: '当前浏览器无法采集实时音频' })
          settleStart(false)
          socket?.close()
        }
      } catch (error) {
        handlers.onFallback?.({ message: error.message || '实时音频启动失败' })
        settleStart(false)
        socket?.close()
      }
    }
    socket.onmessage = handleMessage
    socket.onerror = () => {
      handlers.onFallback?.({ message: '实时识别连接失败' })
      settleStart(false)
      try { socket?.close() } catch (_) {}
    }
    socket.onclose = () => {
      const unexpected = !closing && ready
      cleanup()
      if (unexpected) handlers.onFallback?.({ message: '实时识别已断开，切换分片识别' })
      settleStart(false)
      handlers.onClose?.()
    }
  } catch (error) {
    settleStart(false, error)
    cleanup()
  }
  return pendingStart
  // #endif
  // #ifndef H5
  return Promise.resolve(false)
  // #endif
}

function stopSocket(controlType) {
  // #ifdef H5
  closing = true
  stopPcmCapture()
  if (!socket || socket.readyState > WebSocket.OPEN) {
    cleanup()
    return Promise.resolve(false)
  }
  return new Promise((resolve) => {
    const target = socket
    const timeout = setTimeout(() => {
      try { target.close() } catch (_) {}
      cleanup()
      resolve(false)
    }, 12000)
    const originalClose = target.onclose
    target.onclose = (event) => {
      clearTimeout(timeout)
      originalClose?.(event)
      resolve(true)
    }
    if (target.readyState === WebSocket.OPEN) {
      target.send(JSON.stringify({ type: controlType }))
    } else {
      try { target.close() } catch (_) {
        clearTimeout(timeout)
        cleanup()
        resolve(false)
      }
    }
  })
  // #endif
  // #ifndef H5
  return Promise.resolve(false)
  // #endif
}

export function stopRealtimeSpeech() { return stopSocket('finish') }
export function abortRealtimeSpeech() { return stopSocket('cancel') }

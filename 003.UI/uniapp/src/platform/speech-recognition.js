// Auralis 智听 — H5 实时语音识别适配。
// 原生 App/小程序没有统一的 Web Speech API，返回 false 交由服务端 ASR。

let recognition = null
let shouldRun = false
let recognitionStarted = false
let restartTimer = null
let stopResolver = null
let handlers = {}

const LOCALES = {
  en: 'en-US',
  de: 'de-DE',
  fr: 'fr-FR',
  es: 'es-ES',
  pt: 'pt-PT',
  it: 'it-IT',
  ja: 'ja-JP',
  ko: 'ko-KR',
  ru: 'ru-RU',
  th: 'th-TH',
  vi: 'vi-VN',
  ar: 'ar-SA',
  hi: 'hi-IN',
  tr: 'tr-TR',
  'zh-CN': 'zh-CN',
}

function recognitionLocale(code) {
  return LOCALES[code] || code || 'en-US'
}

function isMobileBrowser() {
  if (typeof navigator === 'undefined') return false
  const userAgent = navigator.userAgent || ''
  return /Android|iPhone|iPad|iPod|Mobile|MicroMessenger/i.test(userAgent)
}

export function isSpeechRecognitionSupported() {
  // #ifdef H5
  return typeof window !== 'undefined'
    && Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)
    // Android WebView、微信内置浏览器等环境可能暴露 Web Speech 接口，
    // 但启动后既不返回结果也不触发错误。移动端统一交给已录音分片的
    // 服务端 ASR，避免页面永久停留在“正在聆听”。
    && !isMobileBrowser()
  // #endif
  // #ifndef H5
  return false
  // #endif
}

// #ifdef H5
function createRecognition(language) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  const instance = new SpeechRecognition()
  instance.lang = recognitionLocale(language)
  instance.interimResults = true
  instance.continuous = true
  instance.maxAlternatives = 1

  instance.onstart = () => {
    recognitionStarted = true
    handlers.onStart?.()
  }

  instance.onresult = (event) => {
    let interimText = ''
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const text = event.results[index]?.[0]?.transcript?.trim()
      if (!text) continue
      if (event.results[index].isFinal) handlers.onFinal?.(text)
      else interimText += `${text} `
    }
    handlers.onInterim?.(interimText.trim())
  }

  instance.onerror = (event) => {
    const fatal = ['not-allowed', 'service-not-allowed', 'audio-capture', 'network'].includes(event.error)
    if (fatal) shouldRun = false
    handlers.onError?.({ code: event.error || 'unknown', fatal })
  }

  instance.onend = () => {
    recognitionStarted = false
    if (stopResolver) {
      const resolve = stopResolver
      stopResolver = null
      resolve(true)
    }
    if (shouldRun) {
      clearTimeout(restartTimer)
      restartTimer = setTimeout(() => {
        if (!shouldRun || !recognition) return
        try { recognition.start() } catch (_) {}
      }, 250)
    }
  }

  return instance
}
// #endif

export async function startSpeechRecognition(options = {}) {
  // #ifdef H5
  if (!isSpeechRecognitionSupported()) return false
  handlers = options
  shouldRun = true
  clearTimeout(restartTimer)
  if (recognition) {
    try { recognition.abort() } catch (_) {}
  }
  recognition = createRecognition(options.language)
  try {
    recognition.start()
    return true
  } catch (error) {
    shouldRun = false
    recognition = null
    throw error
  }
  // #endif
  // #ifndef H5
  return false
  // #endif
}

export function stopSpeechRecognition() {
  // #ifdef H5
  shouldRun = false
  clearTimeout(restartTimer)
  handlers.onInterim?.('')
  if (!recognition || !recognitionStarted) return Promise.resolve(false)
  return new Promise((resolve) => {
    let settled = false
    const finish = (value) => {
      if (settled) return
      settled = true
      if (stopResolver === finish) stopResolver = null
      resolve(value)
    }
    stopResolver = finish
    setTimeout(() => finish(false), 1200)
    try { recognition.stop() } catch (_) { finish(false) }
  })
  // #endif
  // #ifndef H5
  return Promise.resolve(false)
  // #endif
}

export async function resumeSpeechRecognition(options = handlers) {
  return startSpeechRecognition(options)
}

export function abortSpeechRecognition() {
  shouldRun = false
  clearTimeout(restartTimer)
  // #ifdef H5
  if (recognition) {
    try { recognition.abort() } catch (_) {}
  }
  // #endif
  recognition = null
  recognitionStarted = false
  handlers = {}
  if (stopResolver) stopResolver(false)
  stopResolver = null
}

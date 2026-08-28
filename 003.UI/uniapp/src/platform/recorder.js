// Auralis 智听 — 录音平台适配（H5 / App / 微信小程序）

const RECORD_OPTIONS = {
  duration: 8000,
  sampleRate: 16000,
  numberOfChannels: 1,
  encodeBitRate: 64000,
  format: 'wav',
}

let manager = null
let initialized = false
let active = false
let started = false
let stopResolver = null
let stopRejecter = null
let startResolver = null
let startRejecter = null
let segmentHandler = null

// #ifndef H5
// ─── 原生平台：uni.getRecorderManager ─────────────────

function getManager() {
  if (!manager) manager = uni.getRecorderManager()
  if (!initialized) {
    initialized = true
    manager.onStart(() => {
      started = true
      if (startResolver) startResolver(true)
      startResolver = null
      startRejecter = null
    })
    manager.onStop(async (result) => {
      started = false
      const tempFilePath = result?.tempFilePath || ''
      let segment = null
      try {
        segment = await preserveNativeSegment(tempFilePath)
      } catch (error) {
        if (stopRejecter) stopRejecter(error)
        stopResolver = null
        stopRejecter = null
        if (active) {
          try { await startNative() } catch (_) { active = false }
        }
        uni.showToast({ title: error.message || '录音分段保存失败', icon: 'none' })
        return
      }
      if (stopResolver) {
        const resolve = stopResolver
        stopResolver = null
        stopRejecter = null
        resolve(segment)
        return
      }
      if (active) {
        const pendingSegment = segment && segmentHandler
          ? Promise.resolve().then(() => segmentHandler(segment))
          : Promise.resolve()
        try { if (active) await startNative() }
        catch (error) {
          active = false
          uni.showToast({ title: error.message || '录音分段保存失败', icon: 'none' })
        }
        pendingSegment.catch((error) => {
          uni.showToast({ title: error.message || '录音分段保存失败', icon: 'none' })
        })
      } else if (segment) {
        segment.cleanup()
      }
    })
    manager.onError((error) => {
      started = false
      active = false
      if (startRejecter) startRejecter(new Error(error?.errMsg || '录音启动失败'))
      if (stopRejecter) stopRejecter(new Error(error?.errMsg || '录音失败'))
      startResolver = null
      startRejecter = null
      stopResolver = null
      stopRejecter = null
    })
  }
  return manager
}

/**
 * App 运行基座可能在下一次录音时复用临时文件。先移到唯一的应用
 * 保存目录，确保上传队列稍后读取时路径仍然有效。上传完成后由调用方清理。
 */
function preserveNativeSegment(tempFilePath) {
  if (!tempFilePath || typeof tempFilePath !== 'string') {
    return Promise.reject(new Error('录音未生成可用的本地文件'))
  }

  // #ifdef APP-PLUS
  return new Promise((resolve, reject) => {
    uni.saveFile({
      tempFilePath,
      success: (result) => {
        const filePath = result?.savedFilePath || ''
        if (!filePath) {
          reject(new Error('录音文件保存失败'))
          return
        }
        let cleaned = false
        resolve({
          filePath,
          cleanup() {
            if (cleaned) return
            cleaned = true
            uni.removeSavedFile({ filePath, fail: () => {} })
          },
        })
      },
      fail: (error) => reject(new Error(error?.errMsg || '录音文件保存失败')),
    })
  })
  // #endif

  // #ifndef APP-PLUS
  return Promise.resolve({ filePath: tempFilePath, cleanup() {} })
  // #endif
}

function startNative() {
  return new Promise((resolve, reject) => {
    startResolver = resolve
    startRejecter = reject
    try { getManager().start(RECORD_OPTIONS) }
    catch (error) {
      startResolver = null
      startRejecter = null
      reject(error)
    }
  })
}

export function ensureRecordPermission() {
  // #ifdef MP-WEIXIN
  return new Promise((resolve, reject) => {
    uni.getSetting({
      success: (settings) => {
        if (settings.authSetting['scope.record'] === true) return resolve(true)
        if (settings.authSetting['scope.record'] === false) {
          uni.openSetting({
            success: (result) => result.authSetting['scope.record'] ? resolve(true) : reject(new Error('请在设置中允许麦克风权限')),
            fail: () => reject(new Error('无法打开权限设置')),
          })
          return
        }
        uni.authorize({ scope: 'scope.record', success: () => resolve(true), fail: () => reject(new Error('麦克风权限被拒绝')) })
      },
      fail: () => reject(new Error('无法检查麦克风权限')),
    })
  })
  // #endif
  // #ifndef MP-WEIXIN
  return Promise.resolve(true)
  // #endif
}

export async function startCapture(onSegment) {
  await ensureRecordPermission()
  segmentHandler = onSegment || null
  active = true
  await startNative()
}

function stopCurrentSegment() {
  if (!started) return Promise.resolve('')
  return new Promise((resolve, reject) => {
    stopResolver = resolve
    stopRejecter = reject
    getManager().stop()
  })
}

export async function pauseCapture() {
  active = false
  return stopCurrentSegment()
}

export async function resumeCapture(onSegment) {
  segmentHandler = onSegment || segmentHandler
  active = true
  await startNative()
}

export async function finishCapture() {
  active = false
  const filePath = await stopCurrentSegment()
  segmentHandler = null
  return filePath
}

export function abortCapture() {
  active = false
  segmentHandler = null
  if (started) {
    try { getManager().stop() } catch (_) {}
  }
}

export function startPcmCapture() {
  return Promise.resolve(false)
}

export function stopPcmCapture() {}

// #endif

// #ifdef H5
// ─── H5 浏览器：MediaRecorder API ─────────────────────

let mediaStream = null
let mediaRecorder = null
let currentMimeType = 'audio/webm'
let segmentTimer = null
let chunkIndex = 0
let restartPromise = null
const H5_SEGMENT_DURATION = 4000
const PCM_SAMPLE_RATE = 16000
const PCM_FRAME_BYTES = 5120
let pcmAudioContext = null
let pcmSource = null
let pcmProcessor = null
let pcmPending = new Int16Array(0)
let pcmFrameHandler = null

export function ensureRecordPermission() {
  if (!window.isSecureContext) {
    return Promise.reject(new Error('手机浏览器录音需要 HTTPS，请使用安全地址重新打开'))
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    return Promise.reject(new Error('当前浏览器不支持麦克风录音，请使用最新版 Chrome 或 Safari'))
  }
  if (typeof MediaRecorder === 'undefined') {
    return Promise.reject(new Error('当前浏览器不支持音频录制，请使用最新版 Chrome 或 Safari'))
  }
  return navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    // 先释放权限测试流；正式录音时重新获取。
    stream.getTracks().forEach((track) => track.stop())
    return true
  }).catch((error) => {
    if (error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError') {
      throw new Error('麦克风权限被拒绝，请在浏览器网站设置中允许麦克风')
    }
    if (error?.name === 'NotFoundError' || error?.name === 'DevicesNotFoundError') {
      throw new Error('未检测到可用麦克风')
    }
    throw new Error('麦克风不可用，请检查浏览器和系统权限')
  })
}

function getSupportedMimeType() {
  const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
  for (const t of types) {
    if (typeof MediaRecorder.isTypeSupported !== 'function' || MediaRecorder.isTypeSupported(t)) return t
  }
  return ''
}

async function ensureStream() {
  if (!mediaStream) {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true },
    })
  }
  return mediaStream
}

function releaseStream() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop())
    mediaStream = null
  }
}

async function startMediaRecorder() {
  const stream = await ensureStream()
  if (!active) throw new Error('录音已停止')
  return new Promise((resolve, reject) => {
    try {
      currentMimeType = getSupportedMimeType()
      const options = { audioBitsPerSecond: 64000 }
      if (currentMimeType) options.mimeType = currentMimeType
      mediaRecorder = new MediaRecorder(stream, options)
      currentMimeType = mediaRecorder.mimeType || currentMimeType || 'audio/webm'
      const chunks = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) chunks.push(event.data)
      }

      mediaRecorder.onstart = () => {
        started = true
        resolve(true)
        segmentTimer = setTimeout(() => {
          if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.requestData()
            // 停止当前段，onstop 会自动切分并重启下一段
            mediaRecorder.stop()
          }
        }, H5_SEGMENT_DURATION)
      }

      mediaRecorder.onstop = async () => {
        clearTimeout(segmentTimer)
        const ext = currentMimeType.includes('webm') ? 'webm' : currentMimeType.includes('ogg') ? 'ogg' : currentMimeType.includes('mp4') ? 'm4a' : 'webm'
        const file = new File(chunks.splice(0), `segment_${chunkIndex++}.${ext}`, { type: currentMimeType })
        started = false

        if (stopResolver) {
          const resolve = stopResolver
          stopResolver = null
          stopRejecter = null
          resolve(file)
          return
        }

        // 立即把分片交给页面队列（不等待网络），确保停止课堂前 uploadChain
        // 已包含这一段；随后马上启动下一段，避免上传期间漏录。
        if (file.size > 0 && segmentHandler) {
          try {
            Promise.resolve(segmentHandler(file)).catch((error) => {
              uni.showToast({ title: error.message || '录音分段保存失败', icon: 'none' })
            })
          } catch (error) {
            uni.showToast({ title: error.message || '录音分段保存失败', icon: 'none' })
          }
        }

        // 先开始下一段，避免等待上传时漏录；上一段由页面串行上传。
        if (active) {
          try {
            restartPromise = startMediaRecorder()
            await restartPromise
          }
          catch (error) {
            active = false
            if (error.message !== '录音已停止') {
              uni.showToast({ title: error.message || '录音分段保存失败', icon: 'none' })
            }
          } finally {
            restartPromise = null
          }
        }
      }

      mediaRecorder.onerror = (event) => {
        started = false
        active = false
        clearTimeout(segmentTimer)
        const err = new Error(event?.error?.message || '录音失败')
        reject(err)
        if (stopRejecter) { stopRejecter(err); stopResolver = null; stopRejecter = null }
      }

      mediaRecorder.start(1000) // 每秒收集一次数据
    } catch (error) {
      reject(error)
    }
  })
}

export async function startCapture(onSegment) {
  await ensureRecordPermission()
  segmentHandler = onSegment || null
  active = true
  chunkIndex = 0
  await startMediaRecorder()
}

function stopCurrent() {
  if (restartPromise) return restartPromise.catch(() => null).then(() => stopCurrent())
  if (!mediaRecorder) return Promise.resolve(null)
  // MediaRecorder.stop() 会立即切为 inactive，onstop 稍后才带回数据。
  // 此时等待正在结束的分片，避免上传空文件或漏掉最后一段。
  if (mediaRecorder.state === 'inactive') {
    if (!started) return Promise.resolve(null)
    return new Promise((resolve, reject) => {
      stopResolver = resolve
      stopRejecter = reject
    })
  }
  return new Promise((resolve, reject) => {
    stopResolver = resolve
    stopRejecter = reject
    clearTimeout(segmentTimer)
    mediaRecorder.requestData()
    mediaRecorder.stop()
  })
}

export async function pauseCapture() {
  active = false
  return stopCurrent()
}

export async function resumeCapture(onSegment) {
  segmentHandler = onSegment || segmentHandler
  active = true
  await startMediaRecorder()
}

export async function finishCapture() {
  active = false
  const blob = await stopCurrent()
  segmentHandler = null
  releaseStream()
  return blob
}

export function abortCapture() {
  active = false
  segmentHandler = null
  clearTimeout(segmentTimer)
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    try { mediaRecorder.stop() } catch (_) {}
  }
  releaseStream()
}

function downsampleTo16k(floatSamples, inputRate) {
  if (inputRate === PCM_SAMPLE_RATE) return floatSamples
  const ratio = inputRate / PCM_SAMPLE_RATE
  const outputLength = Math.max(1, Math.round(floatSamples.length / ratio))
  const output = new Float32Array(outputLength)
  for (let index = 0; index < outputLength; index += 1) {
    const start = Math.floor(index * ratio)
    const end = Math.min(floatSamples.length, Math.floor((index + 1) * ratio))
    let sum = 0
    for (let cursor = start; cursor < end; cursor += 1) sum += floatSamples[cursor]
    output[index] = sum / Math.max(1, end - start)
  }
  return output
}

function floatToInt16(samples) {
  const output = new Int16Array(samples.length)
  for (let index = 0; index < samples.length; index += 1) {
    const value = Math.max(-1, Math.min(1, samples[index]))
    output[index] = value < 0 ? value * 0x8000 : value * 0x7fff
  }
  return output
}

function appendPcm(samples) {
  const combined = new Int16Array(pcmPending.length + samples.length)
  combined.set(pcmPending)
  combined.set(samples, pcmPending.length)
  pcmPending = combined
  const samplesPerFrame = PCM_FRAME_BYTES / 2
  while (pcmPending.length >= samplesPerFrame) {
    const frame = pcmPending.slice(0, samplesPerFrame)
    pcmPending = pcmPending.slice(samplesPerFrame)
    pcmFrameHandler?.(frame.buffer)
  }
}

export async function startPcmCapture(onFrame) {
  if (pcmProcessor) return true
  const stream = await ensureStream()
  const AudioContextClass = window.AudioContext || window.webkitAudioContext
  if (!AudioContextClass) return false
  pcmFrameHandler = onFrame
  pcmPending = new Int16Array(0)
  pcmAudioContext = new AudioContextClass()
  if (pcmAudioContext.state === 'suspended') await pcmAudioContext.resume()
  pcmSource = pcmAudioContext.createMediaStreamSource(stream)
  // ScriptProcessor 在微信 WebView 和旧版移动浏览器中的覆盖率高于 AudioWorklet。
  // 只用于本地采样转换，网络发送仍按百度建议的 160ms/5120 字节帧进行。
  pcmProcessor = pcmAudioContext.createScriptProcessor(4096, 1, 1)
  pcmProcessor.onaudioprocess = (event) => {
    if (!pcmFrameHandler) return
    const input = event.inputBuffer.getChannelData(0)
    appendPcm(floatToInt16(downsampleTo16k(input, pcmAudioContext.sampleRate)))
  }
  pcmSource.connect(pcmProcessor)
  pcmProcessor.connect(pcmAudioContext.destination)
  return true
}

export function stopPcmCapture() {
  pcmFrameHandler = null
  pcmPending = new Int16Array(0)
  if (pcmProcessor) {
    pcmProcessor.onaudioprocess = null
    try { pcmProcessor.disconnect() } catch (_) {}
  }
  if (pcmSource) {
    try { pcmSource.disconnect() } catch (_) {}
  }
  if (pcmAudioContext) {
    try { pcmAudioContext.close() } catch (_) {}
  }
  pcmProcessor = null
  pcmSource = null
  pcmAudioContext = null
}

// #endif

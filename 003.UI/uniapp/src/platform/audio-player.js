import { absoluteAssetUrl } from '../config/env'

export function createAudioPlayer(callbacks = {}) {
  const audio = uni.createInnerAudioContext()
  audio.autoplay = false
  audio.obeyMuteSwitch = false
  audio.onCanplay(() => callbacks.onReady?.(audio.duration || 0))
  audio.onPlay(() => callbacks.onState?.(true))
  audio.onPause(() => callbacks.onState?.(false))
  audio.onStop(() => callbacks.onState?.(false))
  audio.onEnded(() => callbacks.onState?.(false))
  audio.onTimeUpdate(() => callbacks.onTime?.(audio.currentTime || 0, audio.duration || 0))
  audio.onError((error) => callbacks.onError?.(error))

  return {
    setSource(url) { audio.src = absoluteAssetUrl(url) },
    play() { audio.play() },
    pause() { audio.pause() },
    seek(seconds) { audio.seek(Math.max(0, seconds)) },
    setRate(rate) { audio.playbackRate = rate },
    get currentTime() { return audio.currentTime || 0 },
    get duration() { return audio.duration || 0 },
    destroy() { audio.destroy() },
  }
}

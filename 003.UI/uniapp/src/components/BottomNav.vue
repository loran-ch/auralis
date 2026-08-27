<template>
  <view class="bottom-nav">
    <view class="nav-inner content-wide">
      <view v-for="item in items" :key="item.key" class="nav-item" :class="{ active: normalizedActive === item.key }" @tap="navigate(item)">
        <text class="nav-icon">{{ item.icon }}</text>
        <text class="nav-label">{{ item.label }}</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ active: { type: String, required: true } })
const normalizedActive = computed(() => props.active === 'cards' ? 'history' : props.active)
const items = [
  { key: 'courses', label: '课程', icon: '▦', url: '/pages/courses/index' },
  { key: 'history', label: '记录', icon: '◷', url: '/pages/history/index' },
  { key: 'recorder', label: '录音', icon: '●', url: '/pages/recorder/index' },
  { key: 'assistant', label: '助手', icon: '✦', url: '/pages/assistant/index' },
  { key: 'profile', label: '我的', icon: '♙', url: '/pages/profile/index' },
]

function navigate(item) {
  uni.reLaunch({ url: item.url })
}
</script>

<style scoped>
.bottom-nav { position: fixed; z-index: 70; left: 0; right: 0; bottom: 0; padding-bottom: env(safe-area-inset-bottom); background: var(--card); border-top: 1rpx solid rgba(193,199,210,.35); box-shadow: 0 -6rpx 24rpx rgba(26,28,29,.05); }
.nav-inner { height: 128rpx; display: flex; align-items: center; justify-content: space-around; }
.nav-item { width: 20%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--muted); }
.nav-item.active { color: var(--primary); }
.nav-icon { width: 72rpx; height: 52rpx; border-radius: 999rpx; display: flex; align-items: center; justify-content: center; font-size: 32rpx; font-weight: 800; }
.active .nav-icon { background: rgba(0,94,161,.12); }
.nav-label { margin-top: 6rpx; font-size: 20rpx; font-weight: 700; }
</style>

<template>
  <view class="header-wrap">
    <view class="safe-top" />
    <view class="app-header content-wide">
      <button v-if="back" class="header-button" @tap="goBack">‹</button>
      <button v-else-if="menu" class="header-button" @tap="$emit('menu')">☰</button>
      <view v-else class="header-spacer" />
      <view class="header-title-wrap">
        <text class="header-title">{{ title }}</text>
        <text v-if="subtitle" class="header-subtitle">{{ subtitle }}</text>
      </view>
      <view class="header-action"><slot name="right" /></view>
    </view>
  </view>
</template>

<script setup>
const props = defineProps({
  title: { type: String, default: 'LiveTrans Voice' },
  subtitle: { type: String, default: '' },
  back: { type: Boolean, default: false },
  menu: { type: Boolean, default: false },
  fallback: { type: String, default: '/pages/recorder/index' },
})
defineEmits(['menu'])

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.reLaunch({ url: props.fallback })
}
</script>

<style scoped>
.header-wrap { position: sticky; top: 0; z-index: 60; background: var(--surface); border-bottom: 1rpx solid rgba(193,199,210,.25); }
.safe-top { height: env(safe-area-inset-top); }
.app-header { height: 112rpx; padding: 0 24rpx; display: flex; align-items: center; }
.header-button, .header-spacer, .header-action { width: 84rpx; height: 84rpx; padding: 0; background: transparent; color: var(--primary); display: flex; align-items: center; justify-content: center; font-size: 52rpx; line-height: 1; }
.header-action { margin-left: auto; }
.header-title-wrap { flex: 1; min-width: 0; padding: 0 10rpx; }
.header-title { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 32rpx; font-weight: 800; color: var(--text); }
.header-subtitle { display: block; margin-top: 4rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 20rpx; color: var(--muted); }
</style>

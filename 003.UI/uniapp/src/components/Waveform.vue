<template>
  <view class="waveform" :class="{ active }">
    <view v-for="index in 22" :key="index" class="bar" :style="{ height: heights[index - 1] + 'rpx', animationDelay: `${(index % 7) * 70}ms` }" />
  </view>
</template>

<script setup>
defineProps({ active: { type: Boolean, default: false } })
const heights = Array.from({ length: 22 }, (_, index) => 12 + ((index * 29) % 46))
</script>

<style scoped>
.waveform { height: 76rpx; display: flex; align-items: center; justify-content: center; gap: 7rpx; }
.bar { width: 7rpx; min-height: 10rpx; border-radius: 999rpx; background: var(--primary); opacity: .5; transform: scaleY(.45); }
.active .bar { opacity: 1; animation: wave .72s ease-in-out infinite alternate; }
@keyframes wave { from { transform: scaleY(.35); } to { transform: scaleY(1); } }
</style>

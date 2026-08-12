<template>
  <view v-if="modelValue" class="modal-mask" @tap.self="close">
    <view class="modal-sheet">
      <view class="row-between title-row">
        <text class="section-title">选择收藏标签</text>
        <text class="close" @tap="close">×</text>
      </view>
      <view class="tag-list">
        <view v-for="tag in tags" :key="tag.value" class="tag-option" @tap="select(tag.value)">
          <text class="tag-icon">{{ tag.icon }}</text>
          <view><text class="tag-name">{{ tag.label }}</text><text class="tag-desc">{{ tag.desc }}</text></view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'select'])
const tags = [
  { value: 'important', label: '重要', icon: '⭐', desc: '需要重点回顾' },
  { value: 'question', label: '疑问', icon: '❓', desc: '课后需要查证' },
  { value: 'exam', label: '考点', icon: '🎯', desc: '可能出现在考试中' },
  { value: 'definition', label: '定义', icon: '📘', desc: '概念与术语解释' },
]
function close() { emit('update:modelValue', false) }
function select(value) { emit('select', value); close() }
</script>

<style scoped>
.title-row { margin-bottom: 28rpx; }
.close { width: 64rpx; height: 64rpx; text-align: center; line-height: 58rpx; font-size: 48rpx; color: var(--muted); }
.tag-list { display: flex; flex-wrap: wrap; gap: 20rpx; }
.tag-option { width: calc(50% - 10rpx); min-height: 126rpx; padding: 24rpx; display: flex; align-items: center; gap: 20rpx; border-radius: 24rpx; background: var(--surface-low); }
.tag-icon { font-size: 38rpx; }
.tag-name, .tag-desc { display: block; }
.tag-name { font-weight: 700; color: var(--text); }
.tag-desc { margin-top: 6rpx; font-size: 20rpx; color: var(--muted); }
</style>

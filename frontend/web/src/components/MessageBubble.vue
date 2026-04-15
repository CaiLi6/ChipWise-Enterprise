<script setup lang="ts">
import type { Citation } from '@/types/api'
import CitationCard from './CitationCard.vue'

defineProps<{
  role: 'user' | 'assistant' | 'system'
  content: string
  citations?: Citation[]
  loading?: boolean
}>()
</script>

<template>
  <div class="bubble-row" :class="role">
    <!-- 圆形头像 -->
    <div class="avatar">
      {{ role === 'user' ? '我' : role === 'system' ? '系' : 'AI' }}
    </div>

    <!-- 气泡 + 引用 -->
    <div class="bubble-content">
      <div class="bubble-body">
        <span style="white-space: pre-wrap">{{ content }}</span>
        <span v-if="loading" class="cursor">▌</span>
      </div>
      <div v-if="citations && citations.length" class="citations">
        <CitationCard v-for="c in citations" :key="c.chunk_id" :citation="c" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.bubble-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
}

/* 用户消息：头像在右，气泡在左 */
.bubble-row.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
}
.user .avatar {
  background: #409EFF;
}
.assistant .avatar {
  background: #67C23A;
}
.system .avatar {
  background: #F56C6C;
}

.bubble-content {
  display: flex;
  flex-direction: column;
  max-width: 70%;
}
/* 用户侧内容整体右对齐（引用卡片跟随） */
.user .bubble-content {
  align-items: flex-end;
}

.bubble-body {
  padding: 12px 16px;
  border-radius: 8px;
  text-align: left;
  word-break: break-word;
  line-height: 1.6;
}
.user .bubble-body {
  background: #ecf5ff;
  border-radius: 12px 2px 12px 12px;
}
.assistant .bubble-body {
  background: #f0f9eb;
  border-radius: 2px 12px 12px 12px;
}
.system .bubble-body {
  background: #fef0f0;
  color: #f56c6c;
  border-radius: 2px 12px 12px 12px;
}

.citations {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cursor {
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}
</style>

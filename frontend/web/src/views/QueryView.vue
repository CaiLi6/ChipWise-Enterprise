<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useQueryStore } from '@/stores/query'
import { streamQuery } from '@/api/query'
import { Promotion } from '@element-plus/icons-vue'

const store = useQueryStore()
const input = ref('')
const chatContainer = ref<HTMLElement>()

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

function handleSend() {
  const text = input.value.trim()
  if (!text || store.isStreaming) return

  store.addMessage({ role: 'user', content: text })
  store.addMessage({ role: 'assistant', content: '' })
  store.isStreaming = true
  input.value = ''
  scrollToBottom()

  streamQuery(
    { query: text, stream: true },
    (chunk) => {
      store.appendToLast(chunk)
      scrollToBottom()
    },
    () => {
      store.isStreaming = false
    },
  )
}
</script>

<template>
  <div style="display: flex; flex-direction: column; height: 100vh">
    <div style="padding: 16px; border-bottom: 1px solid #ebeef5; font-weight: bold; font-size: 16px">
      智能查询
    </div>
    <div ref="chatContainer" style="flex: 1; overflow-y: auto; padding: 16px">
      <div v-if="store.messages.length === 0" style="text-align: center; color: #909399; padding-top: 100px">
        <h3>欢迎使用 ChipWise 智能查询</h3>
        <p>输入芯片相关问题，例如：STM32F407 的最大主频是多少？</p>
      </div>
      <div v-for="(msg, i) in store.messages" :key="i" style="margin-bottom: 16px">
        <div :style="{ textAlign: msg.role === 'user' ? 'right' : 'left' }">
          <el-tag :type="msg.role === 'user' ? 'primary' : 'success'" size="small" style="margin-bottom: 4px">
            {{ msg.role === 'user' ? '我' : 'ChipWise' }}
          </el-tag>
          <div
            :style="{
              display: 'inline-block',
              maxWidth: '70%',
              padding: '12px 16px',
              borderRadius: '8px',
              background: msg.role === 'user' ? '#ecf5ff' : '#f0f9eb',
              textAlign: 'left',
              whiteSpace: 'pre-wrap',
            }"
          >
            {{ msg.content }}<span v-if="store.isStreaming && i === store.messages.length - 1" class="cursor">▌</span>
          </div>
        </div>
      </div>
    </div>
    <div style="padding: 16px; border-top: 1px solid #ebeef5; display: flex; gap: 8px">
      <el-input
        v-model="input"
        placeholder="输入芯片查询问题..."
        size="large"
        @keydown.enter="handleSend"
      />
      <el-button type="primary" size="large" :loading="store.isStreaming" @click="handleSend">
        <el-icon><Promotion /></el-icon>
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.cursor {
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  50% { opacity: 0; }
}
</style>

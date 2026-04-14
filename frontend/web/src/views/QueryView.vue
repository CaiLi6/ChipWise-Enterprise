<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useQueryStore } from '@/stores/query'
import { streamQuery } from '@/api/query'
import { Promotion } from '@element-plus/icons-vue'
import MessageBubble from '@/components/MessageBubble.vue'

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

async function handleSend() {
  const text = input.value.trim()
  if (!text || store.isStreaming) return

  store.addMessage({ role: 'user', content: text })
  store.addMessage({ role: 'assistant', content: '' })
  store.isStreaming = true
  input.value = ''
  scrollToBottom()

  try {
    // Try streaming first; falls back to standard in dev mock
    streamQuery(
      { query: text },
      (chunk) => {
        store.appendToLast(chunk)
        scrollToBottom()
      },
      () => {
        store.isStreaming = false
      },
    )
  } catch (err: unknown) {
    store.isStreaming = false
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status === 503) {
      store.appendToLast('')
      store.addMessage({
        role: 'user', // replaced below
        content: '后端 LLM 服务暂时不可用（503），请稍后重试',
      })
      // Override role on the last message to 'system' via direct mutation
      const msgs = store.messages
      msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], role: 'assistant', content: '⚠️ 后端 LLM 服务暂时不可用（503），请稍后重试' }
    } else {
      store.appendToLast('查询失败，请重试')
    }
    scrollToBottom()
  }
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
      <MessageBubble
        v-for="(msg, i) in store.messages"
        :key="i"
        :role="msg.role"
        :content="msg.content"
        :citations="msg.citations"
        :loading="store.isStreaming && i === store.messages.length - 1 && msg.role === 'assistant'"
      />
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

import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  citations?: Array<{ chunk_id: string; content: string }>
}

export const useQueryStore = defineStore('query', () => {
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  const sessionId = ref('')

  function addMessage(msg: ChatMessage) {
    messages.value.push(msg)
  }

  function appendToLast(text: string) {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant') {
      last.content += text
    }
  }

  function clearHistory() {
    messages.value = []
    sessionId.value = ''
  }

  return { messages, isStreaming, sessionId, addMessage, appendToLast, clearHistory }
})

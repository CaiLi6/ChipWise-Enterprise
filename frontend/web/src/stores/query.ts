import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Citation } from '@/types/api'

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  citations?: Citation[]
}

export interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}

const STORAGE_KEY = 'chipwise_sessions_v1'
const CURRENT_KEY = 'chipwise_current_session'
const DEFAULT_TITLE = '新对话'
const TITLE_MAX_LEN = 14

function genId(): string {
  return `s_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as ChatSession[]
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function freshSession(): ChatSession {
  return {
    id: genId(),
    title: DEFAULT_TITLE,
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  }
}

export const useQueryStore = defineStore('query', () => {
  const sessions = ref<ChatSession[]>(loadSessions())
  const currentSessionId = ref<string>(localStorage.getItem(CURRENT_KEY) || '')
  const isStreaming = ref(false)

  // Bootstrap: ensure at least one session + valid current pointer
  if (sessions.value.length === 0) {
    const s = freshSession()
    sessions.value.push(s)
    currentSessionId.value = s.id
  } else if (!sessions.value.find((s) => s.id === currentSessionId.value)) {
    currentSessionId.value = sessions.value[0].id
  }

  const currentSession = computed<ChatSession>(
    () => sessions.value.find((s) => s.id === currentSessionId.value) || sessions.value[0],
  )

  const messages = computed<ChatMessage[]>(() => currentSession.value?.messages ?? [])

  const sortedSessions = computed<ChatSession[]>(() =>
    [...sessions.value].sort((a, b) => b.updatedAt - a.updatedAt),
  )

  // Debounced localStorage write — streaming tokens would otherwise
  // thrash the disk on every chunk.
  let persistTimer: ReturnType<typeof setTimeout> | null = null
  function schedulePersist() {
    if (persistTimer) clearTimeout(persistTimer)
    persistTimer = setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions.value))
        localStorage.setItem(CURRENT_KEY, currentSessionId.value)
      } catch {
        // quota errors ignored
      }
      persistTimer = null
    }, 200)
  }

  function newSession(): string {
    const s = freshSession()
    sessions.value.unshift(s)
    currentSessionId.value = s.id
    schedulePersist()
    return s.id
  }

  function switchSession(id: string) {
    if (sessions.value.find((s) => s.id === id)) {
      currentSessionId.value = id
      schedulePersist()
    }
  }

  function deleteSession(id: string) {
    const idx = sessions.value.findIndex((s) => s.id === id)
    if (idx === -1) return
    sessions.value.splice(idx, 1)
    if (currentSessionId.value === id) {
      if (sessions.value.length === 0) {
        const s = freshSession()
        sessions.value.push(s)
        currentSessionId.value = s.id
      } else {
        currentSessionId.value = sessions.value[0].id
      }
    }
    schedulePersist()
  }

  function addMessage(msg: ChatMessage) {
    const s = currentSession.value
    if (!s) return
    s.messages.push(msg)
    s.updatedAt = Date.now()
    // Auto-title from first user message
    if (msg.role === 'user' && (!s.title || s.title === DEFAULT_TITLE)) {
      const clean = msg.content.trim().slice(0, TITLE_MAX_LEN)
      if (clean) s.title = clean
    }
    schedulePersist()
  }

  function appendToLast(text: string) {
    const s = currentSession.value
    if (!s) return
    const last = s.messages[s.messages.length - 1]
    if (last && last.role === 'assistant') {
      last.content += text
      s.updatedAt = Date.now()
      schedulePersist()
    }
  }

  function setLastCitations(citations: Citation[]) {
    const s = currentSession.value
    if (!s) return
    const last = s.messages[s.messages.length - 1]
    if (last && last.role === 'assistant') {
      last.citations = citations
      s.updatedAt = Date.now()
      schedulePersist()
    }
  }

  function clearCurrent() {
    const s = currentSession.value
    if (!s) return
    s.messages = []
    s.title = DEFAULT_TITLE
    s.updatedAt = Date.now()
    schedulePersist()
  }

  return {
    sessions,
    currentSessionId,
    isStreaming,
    currentSession,
    messages,
    sortedSessions,
    newSession,
    switchSession,
    deleteSession,
    addMessage,
    appendToLast,
    setLastCitations,
    clearCurrent,
  }
})

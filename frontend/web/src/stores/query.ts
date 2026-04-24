import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { Citation } from '@/types/api'
import { useAuthStore } from '@/stores/auth'

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

const STORAGE_PREFIX = 'chipwise_sessions_v1'
const CURRENT_PREFIX = 'chipwise_current_session'
const DEFAULT_TITLE = '新对话'
const TITLE_MAX_LEN = 14

function genId(): string {
  return `s_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

// ---------------------------------------------------------------------------
// Per-user storage keys
//
// Conversations are stored in localStorage which is shared across all users on
// the same browser. Without namespacing, logging out as user A and back in as
// user B would let B see A's chat history — a privacy leak. We key every
// session-related entry by the active username.
// ---------------------------------------------------------------------------
function userKey(username: string): string {
  // 'guest' bucket is used before login so that anonymous browsing still works
  // but never bleeds into a real account's history.
  return username && username.trim() ? username.trim() : 'guest'
}

function sessionsKey(username: string): string {
  return `${STORAGE_PREFIX}::${userKey(username)}`
}

function currentKey(username: string): string {
  return `${CURRENT_PREFIX}::${userKey(username)}`
}

function loadSessions(username: string): ChatSession[] {
  try {
    const raw = localStorage.getItem(sessionsKey(username))
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

// One-time legacy migration: if the OLD un-namespaced keys exist, move them
// under the current user's bucket and delete the originals so nobody else
// inherits them. Safe to call repeatedly.
function migrateLegacyKeys(username: string): void {
  try {
    const legacySessions = localStorage.getItem(STORAGE_PREFIX)
    const legacyCurrent = localStorage.getItem(CURRENT_PREFIX)
    if (legacySessions !== null) {
      // Only adopt if the new bucket is empty so we don't overwrite real data.
      if (localStorage.getItem(sessionsKey(username)) === null) {
        localStorage.setItem(sessionsKey(username), legacySessions)
      }
      localStorage.removeItem(STORAGE_PREFIX)
    }
    if (legacyCurrent !== null) {
      if (localStorage.getItem(currentKey(username)) === null) {
        localStorage.setItem(currentKey(username), legacyCurrent)
      }
      localStorage.removeItem(CURRENT_PREFIX)
    }
  } catch {
    // ignore — quota or disabled storage
  }
}

export const useQueryStore = defineStore('query', () => {
  const auth = useAuthStore()

  // Migrate any pre-namespaced data into the current user's bucket once.
  migrateLegacyKeys(auth.username)

  const sessions = ref<ChatSession[]>(loadSessions(auth.username))
  const currentSessionId = ref<string>(
    localStorage.getItem(currentKey(auth.username)) || '',
  )
  const isStreaming = ref(false)

  function bootstrap() {
    if (sessions.value.length === 0) {
      const s = freshSession()
      sessions.value = [s]
      currentSessionId.value = s.id
    } else if (!sessions.value.find((s) => s.id === currentSessionId.value)) {
      currentSessionId.value = sessions.value[0].id
    }
  }

  bootstrap()

  // When the user changes (login, logout, account switch) reload sessions
  // from THAT user's localStorage bucket so we never display another user's
  // history. Critical for privacy on shared browsers.
  watch(
    () => auth.username,
    (newUser) => {
      // Cancel any pending writes to the previous user's bucket.
      if (persistTimer) {
        clearTimeout(persistTimer)
        persistTimer = null
      }
      sessions.value = loadSessions(newUser)
      currentSessionId.value = localStorage.getItem(currentKey(newUser)) || ''
      bootstrap()
    },
  )

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
        localStorage.setItem(sessionsKey(auth.username), JSON.stringify(sessions.value))
        localStorage.setItem(currentKey(auth.username), currentSessionId.value)
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

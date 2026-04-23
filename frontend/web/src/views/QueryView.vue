<script setup lang="ts">
import { ref, nextTick, watch, computed } from 'vue'
import { useQueryStore } from '@/stores/query'
import { useAuthStore } from '@/stores/auth'
import { streamQuery } from '@/api/query'
import MessageBubble from '@/components/MessageBubble.vue'

const store = useQueryStore()
const auth = useAuthStore()
const input = ref('')
const chatContainer = ref<HTMLElement>()
const textareaRef = ref<HTMLTextAreaElement>()

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  })
}

watch(() => store.currentSessionId, () => scrollToBottom())

const greetingName = computed(() => (auth.username || '你').replace(/^[a-z]/, (c) => c.toUpperCase()))
const isEmpty = computed(() => store.messages.length === 0)

function autoSize() {
  const ta = textareaRef.value
  if (!ta) return
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
}

const SUGGESTIONS = [
  { icon: '📈', title: '查询单参数', sub: 'PH2A106FLG900 的 DSP 数量是多少？' },
  { icon: '⚖️', title: '芯片对比',   sub: '对比 PH2A106 和 XCKU5P 的 PCIe 性能' },
  { icon: '🧩', title: '设计规则',   sub: '布线时差分对线长容差是多少？' },
  { icon: '🔧', title: '错误处理',   sub: 'PH2A106 的 PCIe IO 上电时序限制？' },
] as const

function pickSuggestion(text: string) {
  input.value = text
  nextTick(() => textareaRef.value?.focus())
  autoSize()
}

function replaceLastAssistant(text: string) {
  const msgs = store.messages
  const last = msgs[msgs.length - 1]
  if (last && last.role === 'assistant') last.content = text
}

async function handleSend() {
  const text = input.value.trim()
  if (!text || store.isStreaming) return

  store.addMessage({ role: 'user', content: text })
  store.addMessage({ role: 'assistant', content: '' })
  store.isStreaming = true
  input.value = ''
  autoSize()
  scrollToBottom()

  await streamQuery(
    { query: text, session_id: store.currentSessionId },
    (chunk) => { store.appendToLast(chunk); scrollToBottom() },
    (citations) => {
      if (citations && citations.length) store.setLastCitations(citations)
      store.isStreaming = false; scrollToBottom()
    },
    (message) => {
      replaceLastAssistant(message)
      store.isStreaming = false; scrollToBottom()
    },
  )
}

function onEnter(e: KeyboardEvent) {
  if (e.shiftKey) return
  e.preventDefault()
  handleSend()
}
</script>

<template>
  <div class="page">
    <!-- ============== HEADER (minimal, transparent) ============== -->
    <header class="header">
      <div class="model-pill">
        <span class="model-dot" />
        ChipWise <span class="model-suffix">RAG</span>
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="margin-left:4px;opacity:.6"><path d="M6 9l6 6 6-6" stroke-linecap="round"/></svg>
      </div>
    </header>

    <!-- ============== BODY ============== -->
    <div ref="chatContainer" class="body" :class="{ 'is-empty': isEmpty }">
      <!-- Welcome / Hero -->
      <div v-if="isEmpty" class="hero">
        <h1 class="hero-title">
          <span class="grad">你好，{{ greetingName }}</span>
        </h1>
        <p class="hero-sub">今天想了解哪颗芯片？</p>

        <div class="suggestions">
          <button
            v-for="s in SUGGESTIONS" :key="s.title"
            class="suggestion-card"
            @click="pickSuggestion(s.sub)"
          >
            <div class="suggestion-icon">{{ s.icon }}</div>
            <div class="suggestion-text">
              <div class="suggestion-title">{{ s.title }}</div>
              <div class="suggestion-sub">{{ s.sub }}</div>
            </div>
          </button>
        </div>
      </div>

      <!-- Chat messages -->
      <div v-else class="messages">
        <MessageBubble
          v-for="(msg, i) in store.messages"
          :key="i"
          :role="msg.role"
          :content="msg.content"
          :citations="msg.citations"
          :loading="store.isStreaming && i === store.messages.length - 1 && msg.role === 'assistant'"
        />
      </div>
    </div>

    <!-- ============== INPUT (Gemini pill) ============== -->
    <div class="composer-wrap">
      <div class="composer">
        <textarea
          ref="textareaRef"
          v-model="input"
          rows="1"
          :placeholder="store.isStreaming ? '正在生成回答…' : '在此输入问题…'"
          class="composer-input"
          :disabled="store.isStreaming"
          @input="autoSize"
          @keydown.enter="onEnter"
        />
        <div class="composer-actions">
          <button
            class="send-btn"
            :class="{ disabled: !input.trim() && !store.isStreaming, loading: store.isStreaming }"
            :title="store.isStreaming ? '生成中' : '发送 (Enter)'"
            @click="handleSend"
          >
            <svg v-if="!store.isStreaming" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12h14M13 6l6 6-6 6"/>
            </svg>
            <span v-else class="spinner" />
          </button>
        </div>
      </div>
      <p class="footer-hint">ChipWise 可能会犯错，请核对关键参数。Enter 发送，Shift+Enter 换行。</p>
    </div>
  </div>
</template>

<style scoped>
.page {
  height: 100vh;
  display: flex; flex-direction: column;
  background: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
  color: #1f1f1f;
  position: relative;
  overflow: hidden;
}

/* subtle radial gradient on welcome */
.body.is-empty::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 20% 30%, rgba(122, 167, 255, 0.18) 0%, transparent 45%),
    radial-gradient(circle at 80% 20%, rgba(255, 137, 197, 0.14) 0%, transparent 50%),
    radial-gradient(circle at 50% 95%, rgba(168, 130, 255, 0.16) 0%, transparent 60%);
  pointer-events: none;
  z-index: 0;
}

/* ============== HEADER ============== */
.header {
  height: 56px;
  display: flex; align-items: center;
  padding: 0 24px;
  flex-shrink: 0;
  background: transparent;
  z-index: 2;
}
.model-pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 14px;
  border-radius: 999px;
  background: transparent;
  font-size: 14px; color: #444746; font-weight: 500;
  cursor: default;
  transition: background .15s;
}
.model-pill:hover { background: rgba(60, 64, 67, 0.08); }
.model-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: linear-gradient(135deg, #4f8cff, #a16bff);
}
.model-suffix { color: #80868b; font-weight: 400; }

/* ============== BODY ============== */
.body {
  flex: 1;
  overflow-y: auto;
  position: relative;
  z-index: 1;
}
.body.is-empty {
  display: flex; align-items: center; justify-content: center;
}

/* ============== HERO ============== */
.hero {
  width: 100%;
  max-width: 768px;
  padding: 20px 24px 80px;
  text-align: left;
  position: relative;
  z-index: 1;
}
.hero-title {
  font-size: 56px;
  line-height: 1.05;
  font-weight: 500;
  letter-spacing: -0.02em;
  margin: 0 0 4px;
}
.grad {
  background: linear-gradient(90deg, #4f8cff 0%, #a16bff 45%, #ff8ac5 100%);
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
}
.hero-sub {
  font-size: 32px;
  color: #c4c7c5;
  font-weight: 500;
  margin: 0 0 48px;
  letter-spacing: -0.01em;
}

.suggestions {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.suggestion-card {
  text-align: left;
  background: #f0f4f9;
  border: 1px solid transparent;
  border-radius: 16px;
  padding: 16px 16px 18px;
  cursor: pointer;
  transition: background .15s, border-color .15s, transform .08s;
  display: flex; flex-direction: column; gap: 12px;
  min-height: 132px;
  position: relative;
}
.suggestion-card:hover {
  background: #e7edf4;
  border-color: rgba(0,0,0,.04);
}
.suggestion-card:active { transform: translateY(1px); }
.suggestion-icon {
  font-size: 22px; line-height: 1;
  width: 36px; height: 36px;
  background: #fff;
  border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  box-shadow: 0 1px 2px rgba(0,0,0,.06);
}
.suggestion-text { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.suggestion-title { font-size: 14px; font-weight: 500; color: #1f1f1f; }
.suggestion-sub {
  font-size: 13px; color: #5e6368;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ============== MESSAGES ============== */
.messages {
  max-width: 820px;
  margin: 0 auto;
  padding: 24px 24px 24px;
}

/* ============== COMPOSER ============== */
.composer-wrap {
  flex-shrink: 0;
  padding: 12px 24px 16px;
  background: linear-gradient(180deg, rgba(255,255,255,0) 0%, #ffffff 35%);
  z-index: 2;
}
.composer {
  max-width: 820px;
  margin: 0 auto;
  background: #f0f4f9;
  border: 1px solid transparent;
  border-radius: 28px;
  padding: 8px 8px 8px 22px;
  display: flex; align-items: flex-end; gap: 8px;
  box-shadow: 0 1px 2px rgba(0,0,0,.04);
  transition: background .15s, border-color .15s, box-shadow .15s;
}
.composer:focus-within {
  background: #ffffff;
  border-color: rgba(0,0,0,.08);
  box-shadow: 0 1px 6px rgba(60, 64, 67, .15), 0 1px 2px rgba(60, 64, 67, .08);
}
.composer-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font: inherit;
  font-size: 15px;
  color: #1f1f1f;
  line-height: 1.5;
  padding: 12px 0;
  resize: none;
  max-height: 200px;
  overflow-y: auto;
  font-family: inherit;
}
.composer-input::placeholder { color: #80868b; }
.composer-input:disabled { color: #80868b; cursor: not-allowed; }

.composer-actions { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.send-btn {
  width: 40px; height: 40px;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f8cff 0%, #a16bff 100%);
  color: #fff;
  cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  transition: transform .1s, box-shadow .15s, opacity .15s;
  box-shadow: 0 1px 3px rgba(79, 140, 255, .35);
}
.send-btn:hover:not(.disabled):not(.loading) {
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(79, 140, 255, .4);
}
.send-btn.disabled {
  background: #dadce0;
  color: #fff;
  cursor: default;
  box-shadow: none;
  opacity: .8;
}
.send-btn.loading { background: #dadce0; cursor: wait; box-shadow: none; }
.spinner {
  width: 16px; height: 16px;
  border: 2px solid rgba(255,255,255,.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin .8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.footer-hint {
  max-width: 820px;
  margin: 8px auto 0;
  font-size: 11.5px;
  color: #80868b;
  text-align: center;
  letter-spacing: 0.01em;
}

/* scrollbar */
.body::-webkit-scrollbar { width: 8px; }
.body::-webkit-scrollbar-thumb { background: rgba(0,0,0,.10); border-radius: 4px; }
.composer-input::-webkit-scrollbar { width: 5px; }
.composer-input::-webkit-scrollbar-thumb { background: rgba(0,0,0,.15); border-radius: 3px; }

/* responsive */
@media (max-width: 640px) {
  .hero-title { font-size: 40px; }
  .hero-sub { font-size: 22px; margin-bottom: 32px; }
  .suggestions { grid-template-columns: 1fr 1fr; }
  .composer-wrap { padding: 8px 12px 12px; }
  .messages { padding: 16px 12px; }
}
</style>

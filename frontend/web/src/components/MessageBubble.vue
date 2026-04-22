<script setup lang="ts">
import { computed, onMounted, onUpdated, ref, nextTick } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import type { Citation } from '@/types/api'
import CitationCard from './CitationCard.vue'

const props = defineProps<{
  role: 'user' | 'assistant' | 'system'
  content: string
  citations?: Citation[]
  loading?: boolean
}>()

marked.setOptions({ gfm: true, breaks: true })

// Render LaTeX delimiters ($...$, $$...$$, \(...\), \[...\]) using KaTeX.
function renderMath(html: string): string {
  const blockDollar = /\$\$([\s\S]+?)\$\$/g
  const blockBracket = /\\\[([\s\S]+?)\\\]/g
  const inlineDollar = /(?<!\\)\$([^\n$]+?)\$/g
  const inlineParen = /\\\(([\s\S]+?)\\\)/g
  const tryKatex = (tex: string, display: boolean): string => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: display, throwOnError: false })
    } catch {
      return display ? `$$${tex}$$` : `$${tex}$`
    }
  }
  return html
    .replace(blockDollar, (_, tex) => tryKatex(tex, true))
    .replace(blockBracket, (_, tex) => tryKatex(tex, true))
    .replace(inlineParen, (_, tex) => tryKatex(tex, false))
    .replace(inlineDollar, (_, tex) => tryKatex(tex, false))
}

const rendered = computed(() => {
  if (props.role !== 'assistant') return ''
  const raw = props.content || ''
  const html = marked.parse(raw, { async: false }) as string
  const withMath = renderMath(html)
  return DOMPurify.sanitize(withMath, {
    ADD_TAGS: ['math', 'annotation', 'semantics', 'mtext', 'mn', 'mo', 'mi', 'mspace', 'mover', 'munder', 'munderover', 'msup', 'msub', 'msubsup', 'mfrac', 'mroot', 'msqrt', 'mtable', 'mtr', 'mtd', 'mrow', 'mstyle'],
    ADD_ATTR: ['class', 'style', 'aria-hidden'],
  })
})

const bodyRef = ref<HTMLElement>()

const CALLOUT_KEYWORDS = /^(注意|提示|警告|重要|说明|备注|⚠️|💡|📌|note|warning|caution|tip|important)[:：\s]/i

function enhanceContent() {
  if (!bodyRef.value) return

  // 1. Wrap tables in scrollable container
  bodyRef.value.querySelectorAll('table').forEach((t) => {
    if (!t.parentElement?.classList.contains('md-table-wrap')) {
      const wrap = document.createElement('div')
      wrap.className = 'md-table-wrap'
      t.parentElement?.insertBefore(wrap, t)
      wrap.appendChild(t)
    }
  })

  // 2. Detect "注意/警告/提示" headings & paragraphs → mark as callouts
  bodyRef.value.querySelectorAll('h1, h2, h3, h4, h5, h6, p, li').forEach((el) => {
    const text = (el.textContent || '').trim()
    if (CALLOUT_KEYWORDS.test(text) && !el.closest('.md-callout')) {
      el.classList.add('md-callout-title')
    }
  })

  // 3. Strong/emphasis at line start treated as soft-callout label
  bodyRef.value.querySelectorAll('p').forEach((p) => {
    const first = p.firstElementChild
    if (first && first.tagName === 'STRONG' && CALLOUT_KEYWORDS.test(first.textContent || '')) {
      p.classList.add('md-callout-soft')
    }
  })
}
onMounted(() => nextTick(enhanceContent))
onUpdated(() => nextTick(enhanceContent))

const avatarLabel = computed(() => {
  if (props.role === 'user') return '我'
  if (props.role === 'system') return '系'
  return 'AI'
})
</script>

<template>
  <div class="bubble-row" :class="role">
    <div class="avatar" :class="role">
      <span class="avatar-text">{{ avatarLabel }}</span>
    </div>

    <div class="bubble-content">
      <div class="bubble-body" ref="bodyRef">
        <span v-if="role !== 'assistant'" class="plain-text">{{ content }}</span>
        <div v-else class="md" v-html="rendered" />
        <span v-if="loading" class="cursor">▌</span>
      </div>
      <div v-if="citations && citations.length" class="citations">
        <div class="citations-label">
          <span class="citations-label-dot" />
          来源 · {{ citations.length }} 篇引用
        </div>
        <div class="citations-list">
          <CitationCard
            v-for="(c, i) in citations"
            :key="c.chunk_id"
            :citation="c"
            :index="i + 1"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ============================================================
   Layout — pixel-perfect avatar / bubble top-edge alignment
   ============================================================ */
.bubble-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 24px;
}
.bubble-row.user { flex-direction: row-reverse; }

/* ============================================================
   Avatar — clean, subtle, 32px to align with 14px text first line
   ============================================================ */
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px; /* squircle, modern */
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
  color: #fff;
  /* aligns with first line of 14px text @ line-height 1.7 (≈ baseline of bubble padding 14px top) */
  margin-top: 1px;
  user-select: none;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.06);
}
.avatar.user      { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
.avatar.assistant { background: linear-gradient(135deg, #18181b 0%, #27272a 100%); }
.avatar.system    { background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); }
.avatar-text { font-family: ui-sans-serif, system-ui, sans-serif; }

/* ============================================================
   Bubble container & body
   ============================================================ */
.bubble-content {
  display: flex;
  flex-direction: column;
  max-width: 92%;
  min-width: 0;
}
.bubble-row.user .bubble-content {
  align-items: flex-end;
  max-width: 75%;
}

.bubble-body {
  padding: 14px 18px;
  text-align: left;
  word-break: break-word;
  line-height: 1.7;
  overflow-x: auto;
  font-size: 14px;
  letter-spacing: 0.01em;
}

/* — Assistant: white card with whisper-soft elevation — */
.bubble-row.assistant .bubble-body {
  background: #ffffff;
  border: 1px solid #f3f4f6;
  border-radius: 12px;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  color: #374151;
}

/* — User: soft blue tint, mirror radius — */
.bubble-row.user .bubble-body {
  background: #eff6ff;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  color: #1e3a8a;
  font-weight: 450;
}

/* — System: warm amber for non-fatal notice — */
.bubble-row.system .bubble-body {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 12px;
  color: #92400e;
}

.plain-text {
  white-space: pre-wrap;
  font-family: ui-sans-serif, system-ui, sans-serif;
}

/* ============================================================
   Citations footer — quiet, deferential
   ============================================================ */
.citations {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed #f3f4f6;
}
.citations-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #9ca3af;
  font-weight: 500;
  margin-bottom: 10px;
  letter-spacing: 0.01em;
}
.citations-label-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #d1d5db;
}
.citations-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* — Streaming caret — */
.cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: #18181b;
  animation: blink 1.05s step-end infinite;
}
@keyframes blink { 50% { opacity: 0; } }
</style>

<!--
  Unscoped: must style v-html'd Markdown content.
  Scoping IDs are added by Vue when scoped — they do NOT propagate to v-html.
  We namespace everything under .md to avoid leaking globally.
-->
<style>
.md {
  color: #374151;
  font-size: 14px;
  line-height: 1.7;
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

/* ---------- Headings (intimacy principle: tight to content below, breathing room above) ---------- */
.md h1, .md h2, .md h3, .md h4, .md h5, .md h6 {
  font-weight: 600;
  line-height: 1.35;
  color: #111827;
  letter-spacing: -0.01em;
}
.md h1 { font-size: 1.5rem;   margin: 1.75em 0 0.5em; }
.md h2 { font-size: 1.25rem;  margin: 1.6em 0 0.5em; }
.md h3 { font-size: 1.0625rem;margin: 1.4em 0 0.5em; }
.md h4 { font-size: 0.9375rem;margin: 1.2em 0 0.4em; color: #1f2937; }
.md h5, .md h6 { font-size: 0.875rem; margin: 1em 0 0.35em; color: #374151; }
.md > :first-child { margin-top: 0 !important; }
.md > :last-child  { margin-bottom: 0 !important; }

/* ---------- Paragraphs / lists ---------- */
.md p { margin: 0.65em 0; }
.md ul, .md ol { padding-left: 1.5em; margin: 0.65em 0; }
.md li { margin: 0.2em 0; }
.md li > p { margin: 0.2em 0; }
.md li::marker { color: #9ca3af; }
.md strong { color: #111827; font-weight: 600; }
.md em { color: #4b5563; font-style: italic; }
.md hr { border: none; border-top: 1px solid #f3f4f6; margin: 1.6em 0; }
.md a {
  color: #2563eb;
  text-decoration: none;
  border-bottom: 1px solid #bfdbfe;
  transition: border-color 0.15s;
}
.md a:hover { border-bottom-color: #2563eb; }

/* ---------- Inline & block code ---------- */
.md code {
  background: #f3f4f6;
  padding: 0.15em 0.45em;
  border-radius: 4px;
  font-family: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.875em;
  color: #be185d;
  border: none;
  font-weight: 500;
}
.md pre {
  background: #fafafa;
  color: #1f2937;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid #f3f4f6;
  overflow-x: auto;
  margin: 1em 0;
  font-size: 13px;
  line-height: 1.6;
  box-shadow: inset 0 1px 0 rgba(0, 0, 0, 0.02);
}
.md pre code {
  background: transparent;
  color: #1f2937;
  padding: 0;
  border: none;
  font-size: inherit;
  font-weight: 400;
}

/* ---------- Blockquote → soft callout (industry default for chat) ---------- */
.md blockquote {
  background: #eff6ff;
  border-left: 3px solid #3b82f6;
  color: #1e40af;
  padding: 12px 14px 12px 16px;
  margin: 1em 0;
  border-radius: 0 8px 8px 0;
  font-size: 0.9375rem;
  line-height: 1.65;
}
.md blockquote p { margin: 0.25em 0; }
.md blockquote :first-child { margin-top: 0; }
.md blockquote :last-child  { margin-bottom: 0; }

/* ---------- Tables — Vercel-grade minimalism ---------- */
.md-table-wrap {
  overflow-x: auto;
  margin: 1.1em 0;
  border-radius: 10px;
  border: 1px solid #f3f4f6;
  background: #ffffff;
}
.md table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13.5px;
  font-variant-numeric: tabular-nums;
}
.md thead { background: #f9fafb; }
.md th {
  padding: 12px 16px;
  text-align: left;
  font-weight: 500;
  color: #6b7280;
  font-size: 12.5px;
  letter-spacing: 0.02em;
  text-transform: none;
  border-bottom: 1px solid #e5e7eb;
  white-space: nowrap;
}
.md td {
  padding: 12px 16px;
  text-align: left;
  vertical-align: top;
  color: #374151;
  border-bottom: 1px solid #f3f4f6;
}
.md tbody tr:last-child td { border-bottom: none; }
.md tbody tr { transition: background-color 0.12s; }
.md tbody tr:hover { background: #fafafa; }

/* ---------- Callout (auto-detected: 注意 / 警告 / 提示) ---------- */
.md .md-callout-title {
  background: #fef3c7;
  border-left: 3px solid #f59e0b;
  color: #78350f;
  padding: 10px 14px;
  margin: 1em 0 0.6em;
  border-radius: 0 8px 8px 0;
  font-weight: 600;
  font-size: 0.9375rem;
}
.md .md-callout-soft {
  background: #fffbeb;
  border-left: 3px solid #fbbf24;
  padding: 10px 14px;
  border-radius: 0 8px 8px 0;
  color: #713f12;
}
.md .md-callout-soft strong { color: #92400e; }

/* ---------- KaTeX ---------- */
.md .katex { font-size: 1.02em; color: #111827; }
.md .katex-display {
  margin: 1em 0;
  padding: 8px 0;
  overflow-x: auto;
  overflow-y: hidden;
}
</style>

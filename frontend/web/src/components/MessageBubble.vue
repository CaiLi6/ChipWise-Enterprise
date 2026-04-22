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
  // Preserve $ inside code blocks — do math render before markdown so it sits in inline/block
  const html = marked.parse(raw, { async: false }) as string
  const withMath = renderMath(html)
  return DOMPurify.sanitize(withMath, {
    ADD_TAGS: ['math', 'annotation', 'semantics', 'mtext', 'mn', 'mo', 'mi', 'mspace', 'mover', 'munder', 'munderover', 'msup', 'msub', 'msubsup', 'mfrac', 'mroot', 'msqrt', 'mtable', 'mtr', 'mtd', 'mrow', 'mstyle'],
    ADD_ATTR: ['class', 'style', 'aria-hidden'],
  })
})

const bodyRef = ref<HTMLElement>()

function enhanceTables() {
  if (!bodyRef.value) return
  const tables = bodyRef.value.querySelectorAll('table')
  tables.forEach((t) => {
    if (!t.parentElement?.classList.contains('md-table-wrap')) {
      const wrap = document.createElement('div')
      wrap.className = 'md-table-wrap'
      t.parentElement?.insertBefore(wrap, t)
      wrap.appendChild(t)
    }
  })
}
onMounted(() => nextTick(enhanceTables))
onUpdated(() => nextTick(enhanceTables))
</script>

<template>
  <div class="bubble-row" :class="role">
    <div class="avatar">
      {{ role === 'user' ? '我' : role === 'system' ? '系' : 'AI' }}
    </div>

    <div class="bubble-content">
      <div class="bubble-body" ref="bodyRef">
        <span v-if="role !== 'assistant'" style="white-space: pre-wrap">{{ content }}</span>
        <div v-else class="md" v-html="rendered" />
        <span v-if="loading" class="cursor">▌</span>
      </div>
      <div v-if="citations && citations.length" class="citations">
        <div class="citations-label">参考来源（{{ citations.length }}）</div>
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
.bubble-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
}
.bubble-row.user { flex-direction: row-reverse; }

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
.user .avatar { background: #409EFF; }
.assistant .avatar { background: #67C23A; }
.system .avatar { background: #F56C6C; }

.bubble-content {
  display: flex;
  flex-direction: column;
  max-width: 85%;
  min-width: 0;
}
.assistant .bubble-content { max-width: 92%; }
.user .bubble-content { align-items: flex-end; max-width: 70%; }

.bubble-body {
  padding: 14px 18px;
  border-radius: 8px;
  text-align: left;
  word-break: break-word;
  line-height: 1.7;
  overflow-x: auto;
}
.user .bubble-body {
  background: #ecf5ff;
  border-radius: 12px 2px 12px 12px;
}
.assistant .bubble-body {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 2px 12px 12px 12px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
  color: #303133;
  font-size: 14px;
}
.system .bubble-body {
  background: #fef0f0;
  color: #f56c6c;
  border-radius: 2px 12px 12px 12px;
}

.citations {
  margin-top: 10px;
}
.citations-label {
  font-size: 11px;
  color: #909399;
  margin-bottom: 6px;
  letter-spacing: 0.3px;
}
.citations-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cursor { animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }
</style>

<!-- Unscoped: style v-html content -->
<style>
.md { color: #303133; }
.md h1, .md h2, .md h3, .md h4 {
  font-weight: 600;
  margin: 14px 0 8px;
  line-height: 1.4;
  color: #1f2d3d;
}
.md h1 { font-size: 20px; }
.md h2 { font-size: 18px; }
.md h3 { font-size: 16px; }
.md h4 { font-size: 14px; }
.md p { margin: 6px 0; }
.md ul, .md ol { padding-left: 22px; margin: 6px 0; }
.md li { margin: 3px 0; }
.md li > p { margin: 0; }
.md strong { color: #1f2d3d; font-weight: 600; }
.md em { color: #606266; }
.md code {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'JetBrains Mono', Menlo, Consolas, monospace;
  font-size: 12.5px;
  color: #c7254e;
  border: 1px solid #ebeef5;
}
.md pre {
  background: #282c34;
  color: #e5e7eb;
  padding: 12px 14px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 10px 0;
  font-size: 12.5px;
  line-height: 1.55;
}
.md pre code {
  background: transparent;
  color: inherit;
  padding: 0;
  border: none;
  font-size: inherit;
}
.md blockquote {
  border-left: 3px solid #409EFF;
  background: #f0f7ff;
  color: #606266;
  padding: 6px 12px;
  margin: 8px 0;
  border-radius: 2px 4px 4px 2px;
}
.md hr { border: none; border-top: 1px solid #ebeef5; margin: 12px 0; }
.md a { color: #409EFF; text-decoration: none; }
.md a:hover { text-decoration: underline; }

.md-table-wrap {
  overflow-x: auto;
  margin: 10px 0;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}
.md table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}
.md thead {
  background: #f5f7fa;
}
.md th, .md td {
  border: 1px solid #ebeef5;
  padding: 8px 12px;
  text-align: left;
  vertical-align: top;
}
.md th { font-weight: 600; color: #1f2d3d; }
.md tr:nth-child(even) td { background: #fafbfc; }

.md .katex { font-size: 1.02em; }
.md .katex-display {
  margin: 10px 0;
  overflow-x: auto;
  overflow-y: hidden;
}
</style>

import api from './client'
import type { QueryRequest, QueryResponse, Citation } from '@/types/api'

export async function sendQuery(data: QueryRequest): Promise<QueryResponse> {
  const resp = await api.post<QueryResponse>('/api/v1/query', data)
  return resp.data
}

/**
 * Stream a query via POST + SSE. Backend endpoint (`/api/v1/query/stream`) is
 * POST-only, so we can't use `EventSource` (which is GET-only) — use `fetch`
 * with a `ReadableStream` body and parse SSE frames manually.
 *
 * Backend frame format (one per event, separated by blank line):
 *   data: {"type": "token", "content": "word "}
 *   data: {"type": "done",  "citations": [...], "trace_id": "..."}
 *   data: {"type": "error", "content": "..."}
 */
export async function streamQuery(
  data: QueryRequest,
  onChunk: (text: string) => void,
  onDone: (citations?: Citation[], traceId?: string) => void,
  onError?: (message: string) => void,
): Promise<void> {
  // Dev mock when no backend base URL is configured
  if (import.meta.env.DEV && !import.meta.env.VITE_API_BASE_URL) {
    const mockChunks = [
      'STM32F407 是基于 ARM Cortex-M4 内核的高性能微控制器，',
      '主频最高 168 MHz，内置 1 MB Flash 和 192 KB SRAM。',
      '工作电压 1.8V 至 3.6V，温度范围 -40°C 至 +85°C。',
    ]
    for (const c of mockChunks) {
      await new Promise((r) => setTimeout(r, 250))
      onChunk(c)
    }
    onDone()
    return
  }

  const base = import.meta.env.VITE_API_BASE_URL || ''
  const url = `${base}/api/v1/query/stream`

  // Issues a single fetch with the current token. On 401, transparently refresh
  // and retry exactly once before surfacing an "expired" error to the user.
  async function doFetch(allowRetry: boolean): Promise<Response | null> {
    const token = localStorage.getItem('chipwise_token') || ''
    let resp: Response
    try {
      resp = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          Accept: 'text/event-stream',
        },
        body: JSON.stringify(data),
      })
    } catch {
      onError?.(`无法连接后端 (${base || window.location.origin})`)
      onDone()
      return null
    }
    if (resp.status === 401 && allowRetry) {
      try {
        const { useAuthStore } = await import('@/stores/auth')
        await useAuthStore().refresh()
        return doFetch(false)
      } catch {
        /* fall through to 401 handling below */
      }
    }
    return resp
  }

  const resp = await doFetch(true)
  if (!resp) return

  if (!resp.ok) {
    let detail = ''
    try {
      const body = await resp.json()
      detail = typeof body?.detail === 'string' ? body.detail : ''
    } catch {
      /* body not JSON */
    }
    if (resp.status === 401) onError?.('登录已过期，请重新登录')
    else if (resp.status === 503) onError?.(detail || '⚠️ 后端 LLM 服务暂时不可用（503），请稍后重试')
    else onError?.(detail || `请求失败（HTTP ${resp.status}）`)
    onDone()
    return
  }

  if (!resp.body) {
    onError?.('浏览器不支持流式响应')
    onDone()
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let finished = false

  try {
    while (!finished) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE events separated by blank line
      let sepIdx = buffer.indexOf('\n\n')
      while (sepIdx !== -1) {
        const frame = buffer.slice(0, sepIdx)
        buffer = buffer.slice(sepIdx + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data:')) continue
          const payload = line.slice(5).trim()
          if (!payload) continue
          try {
            const msg = JSON.parse(payload) as {
              type: string
              content?: string
              citations?: Citation[]
              trace_id?: string
            }
            if (msg.type === 'token') {
              onChunk(msg.content || '')
            } else if (msg.type === 'done') {
              onDone(msg.citations, msg.trace_id)
              finished = true
              break
            } else if (msg.type === 'error') {
              onError?.(msg.content || '查询失败')
              finished = true
              break
            }
          } catch {
            // Non-JSON SSE line — fall back to raw text
            onChunk(payload)
          }
        }
        if (finished) break
        sepIdx = buffer.indexOf('\n\n')
      }
    }
    if (!finished) onDone()
  } catch {
    onError?.('数据流中断，请重试')
    onDone()
  } finally {
    try {
      reader.releaseLock()
    } catch {
      /* noop */
    }
  }
}

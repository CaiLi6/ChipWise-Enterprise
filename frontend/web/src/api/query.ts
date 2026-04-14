import api from './client'
import type { QueryRequest, QueryResponse } from '@/types/api'

export async function sendQuery(data: QueryRequest): Promise<QueryResponse> {
  const resp = await api.post<QueryResponse>('/api/v1/query', data)
  return resp.data
}

export function streamQuery(
  data: QueryRequest,
  onChunk: (text: string) => void,
  onDone: () => void,
): EventSource | null {
  // In dev mode without backend, use mock
  if (import.meta.env.DEV) {
    const mockChunks = [
      'STM32F407 是基于 ARM Cortex-M4 内核的高性能微控制器，',
      '主频最高 168 MHz，内置 1 MB Flash 和 192 KB SRAM。',
      '工作电压 1.8V 至 3.6V，温度范围 -40°C 至 +85°C。',
    ]
    let i = 0
    const timer = setInterval(() => {
      if (i < mockChunks.length) {
        onChunk(mockChunks[i])
        i++
      } else {
        clearInterval(timer)
        onDone()
      }
    }, 300)
    return null
  }

  const token = localStorage.getItem('chipwise_token') || ''
  const url = `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/query/stream`
  const es = new EventSource(`${url}?query=${encodeURIComponent(data.query)}&token=${token}`)
  es.onmessage = (event) => onChunk(event.data)
  es.onerror = () => { es.close(); onDone() }
  return es
}

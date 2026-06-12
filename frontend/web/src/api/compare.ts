import api from './client'
import type {
  ChipListResponse,
  CompareRequest,
  CompareResult,
} from '@/types/api'

export async function listChips(q?: string, limit = 50): Promise<ChipListResponse> {
  const params: Record<string, string | number> = { limit }
  if (q) params.q = q
  const resp = await api.get<ChipListResponse>('/api/v1/chips', { params })
  return resp.data
}

export async function compareChips(data: CompareRequest): Promise<CompareResult> {
  // The compare endpoint runs a synchronous LLM analysis (35B model) that can
  // take 40-180s for chips with many parameters — well beyond the global 60s
  // axios timeout. Override the timeout for this request only so the result is
  // not aborted mid-flight (which surfaced to users as "no result").
  const resp = await api.post<CompareResult>('/api/v1/compare', data, {
    timeout: 240000,
  })
  return resp.data
}

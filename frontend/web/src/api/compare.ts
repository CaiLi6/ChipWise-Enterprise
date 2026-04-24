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
  const resp = await api.post<CompareResult>('/api/v1/compare', data)
  return resp.data
}

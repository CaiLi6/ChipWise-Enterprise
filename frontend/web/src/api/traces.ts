import api from './client'

export interface TraceSummary {
  trace_id: string
  status: 'ok' | 'error'
  query: string
  user?: string
  started_at?: number
  duration_ms?: number
  answer_preview: string
  citation_count: number
  iterations: number
  stage_count: number
}

export interface TraceStage {
  index: number
  stage: string
  timestamp?: number
  duration_ms?: number | null
  metadata: Record<string, unknown>
}

export interface TraceDetail {
  trace_id: string
  duration_ms?: number
  summary: TraceSummary
  stages: TraceStage[]
}

export async function listTraces(params: {
  limit?: number
  q?: string
  status?: 'ok' | 'error'
} = {}): Promise<{ total: number; traces: TraceSummary[] }> {
  const resp = await api.get('/api/v1/traces', { params })
  return resp.data
}

export async function getTrace(traceId: string): Promise<TraceDetail> {
  const resp = await api.get<TraceDetail>(`/api/v1/traces/${traceId}`)
  return resp.data
}

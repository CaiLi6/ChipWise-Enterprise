import api from './client'

export const METRICS = [
  'faithfulness',
  'answer_relevancy',
  'context_precision',
  'context_recall',
  'citation_coverage',
  'latency_score',
  'citation_diversity',
  'agent_efficiency',
] as const

export type MetricName = (typeof METRICS)[number]

export interface MetricStats {
  count: number
  mean: number
  median: number
  p10: number
  p90: number
  stdev: number
}

export type MetricSummary = Record<MetricName, MetricStats>

export interface EvaluationSummary {
  total: number
  windows: Record<string, MetricSummary>
  trend_7d_delta: Record<MetricName, number>
  last_evaluated_at: number
}

export interface SeriesPoint {
  ts: number
  value: number
  n: number
}

export interface AggregateResponse {
  bucket_sec: number
  window_sec: number
  n: number
  series: Record<MetricName, SeriesPoint[]>
}

export interface DistributionResponse {
  metric: string
  bin_edges: number[]
  counts: number[]
  n: number
  mean: number
  median: number
}

export interface CompareGroup {
  mean_a: number
  mean_b: number
  delta: number
  n_a: number
  n_b: number
  t: number
  p_approx: number
}

export interface CompareResponse {
  window_a: { from: number; to: number; n: number }
  window_b: { from: number; to: number; n: number }
  metrics: Record<MetricName, CompareGroup>
}

export interface EvaluationRecord {
  eval_id: string
  trace_id: string
  query: string
  answer: string
  contexts: string[]
  ground_truth: string | null
  metrics: Partial<Record<MetricName, number | null>>
  judge_model: string
  mode: string
  batch_id: string | null
  evaluated_at: number
  duration_ms_eval: number
  meta: Record<string, unknown>
}

export interface BatchRun {
  batch_id: string
  started_at: number
  completed_at: number | null
  n_total: number
  n_done: number
  n_failed: number
  judge_model: string
  mode: string
  target: Record<string, unknown>
  aggregate: Record<string, number>
  status: 'running' | 'succeeded' | 'failed' | 'cancelled'
  error: string | null
}

export async function getSummary(): Promise<EvaluationSummary> {
  return (await api.get('/api/v1/evaluations/summary')).data
}

export async function getAggregate(params: { bucket_sec?: number; window_sec?: number; mode?: string } = {}) {
  return (await api.get<AggregateResponse>('/api/v1/evaluations/aggregate', { params })).data
}

export async function getDistribution(params: { metric: MetricName; window_sec?: number; bins?: number; mode?: string }) {
  return (await api.get<DistributionResponse>('/api/v1/evaluations/distribution', { params })).data
}

export async function getCompare(params: { a_from: number; a_to: number; b_from: number; b_to: number; mode?: string }) {
  return (await api.get<CompareResponse>('/api/v1/evaluations/compare', { params })).data
}

export async function getOutliers(params: { metric: MetricName; lt?: number; gt?: number; window_sec?: number; limit?: number }) {
  return (await api.get<{ metric: string; lt: number | null; gt: number | null; n: number; rows: EvaluationRecord[] }>(
    '/api/v1/evaluations/outliers',
    { params },
  )).data
}

export async function getByTrace(traceId: string) {
  return (await api.get<{ trace_id: string; evaluations: EvaluationRecord[] }>(
    `/api/v1/evaluations/by_trace/${traceId}`,
  )).data
}

export async function getRecent(params: { limit?: number; mode?: string } = {}) {
  return (await api.get<{ total: number; rows: EvaluationRecord[] }>(
    '/api/v1/evaluations/recent',
    { params },
  )).data
}

export async function listRuns(limit = 50) {
  return (await api.get<{ total: number; runs: BatchRun[] }>(
    '/api/v1/evaluations/runs',
    { params: { limit } },
  )).data
}

export async function getRun(batchId: string) {
  return (await api.get<{ batch: BatchRun; n_samples: number; samples: EvaluationRecord[] }>(
    `/api/v1/evaluations/runs/${batchId}`,
  )).data
}

export async function triggerRun(body: {
  kind: 'traces' | 'golden'
  judge: 'primary' | 'router'
  trace_ids?: string[]
  since?: number
  until?: number
  limit?: number
  metrics?: MetricName[]
  concurrency?: number
}) {
  return (await api.post<{ batch_id: string; started: boolean; judge: string; kind: string }>(
    '/api/v1/evaluations/run',
    body,
  )).data
}

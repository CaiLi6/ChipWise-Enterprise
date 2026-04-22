import api from './client'

export interface GoldenQA {
  id: string
  question: string
  ground_truth_answer: string
  ground_truth_contexts: string[]
  chip_ids: string[]
  tags: string[]
  created_by: string
  created_at: number
}

export async function listGolden() {
  return (await api.get<{ total: number; rows: GoldenQA[] }>('/api/v1/golden')).data
}

export async function addGolden(body: {
  question: string
  ground_truth_answer: string
  ground_truth_contexts?: string[]
  chip_ids?: string[]
  tags?: string[]
  created_by?: string
}) {
  return (await api.post<GoldenQA>('/api/v1/golden', body)).data
}

export async function patchGolden(
  id: string,
  body: Partial<{
    question: string
    ground_truth_answer: string
    ground_truth_contexts: string[]
    chip_ids: string[]
    tags: string[]
  }>,
) {
  return (await api.patch<GoldenQA>(`/api/v1/golden/${id}`, body)).data
}

export async function deleteGolden(id: string) {
  return (await api.delete<{ ok: boolean; id: string }>(`/api/v1/golden/${id}`)).data
}

export async function runGolden(judge: 'primary' | 'router' = 'primary') {
  return (await api.post<{ batch_id: string; started: boolean }>('/api/v1/golden/run', { judge })).data
}

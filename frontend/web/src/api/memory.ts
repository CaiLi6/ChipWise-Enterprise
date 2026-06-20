import api from './client'

export interface MemoryRecord {
  id: string
  scope: 'user' | 'project'
  owner_key?: string | null
  kind: string
  content: string
  tags: string[]
  source: string
  source_id?: string | null
  status: 'candidate' | 'confirmed' | 'rejected'
  metadata?: Record<string, unknown>
  use_count?: number
  created_at?: string
  updated_at?: string
}

export interface MemoryEpisode {
  id: string
  user_key: string
  session_id: string
  trace_id: string
  query_text: string
  rewritten_query?: string
  tools_used: string[]
  citations: unknown[]
  grounding: Record<string, unknown>
  answer_preview?: string
  outcome: string
  created_at?: string
}

export async function listMemories(params?: {
  scope?: 'user' | 'project'
  status?: 'candidate' | 'confirmed' | 'rejected'
  limit?: number
}): Promise<{ memories: MemoryRecord[]; total: number }> {
  const resp = await api.get('/api/v1/memory', { params })
  return resp.data
}

export async function createMemory(data: {
  scope: 'user' | 'project'
  kind: string
  content: string
  tags?: string[]
  status?: 'candidate' | 'confirmed' | 'rejected'
  metadata?: Record<string, unknown>
}): Promise<{ memory_id: string; status: string }> {
  const resp = await api.post('/api/v1/memory', data)
  return resp.data
}

export async function updateMemoryStatus(
  id: string,
  status: 'candidate' | 'confirmed' | 'rejected',
): Promise<{ memory_id: string; status: string }> {
  const resp = await api.patch(`/api/v1/memory/${id}/status`, { status })
  return resp.data
}

export async function deleteMemory(id: string): Promise<{ memory_id: string; status: string }> {
  const resp = await api.delete(`/api/v1/memory/${id}`)
  return resp.data
}

export async function listEpisodes(params?: {
  session_id?: string
  limit?: number
}): Promise<{ episodes: MemoryEpisode[]; total: number }> {
  const resp = await api.get('/api/v1/memory/episodes', { params })
  return resp.data
}

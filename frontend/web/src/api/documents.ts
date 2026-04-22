import api from './client'
import type { DocumentUpload, DocumentListResponse, DocumentMeta } from '@/types/api'

export async function uploadDocument(file: File, manufacturer = 'unknown'): Promise<DocumentUpload> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('manufacturer', manufacturer)
  const resp = await api.post<DocumentUpload>('/api/v1/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return resp.data
}

export async function listDocuments(page = 1, perPage = 20): Promise<DocumentListResponse> {
  const resp = await api.get<DocumentListResponse>('/api/v1/documents', {
    params: { page, per_page: perPage },
  })
  return resp.data
}

export async function getDocument(docId: number): Promise<DocumentMeta> {
  const resp = await api.get<DocumentMeta>(`/api/v1/documents/${docId}`)
  return resp.data
}

export interface IngestResult {
  doc_id: number
  chip_id: number
  pages: number
  chunks: number
  status: string
}

export async function ingestDocument(docId: number): Promise<IngestResult> {
  const resp = await api.post<IngestResult>(`/api/v1/documents/${docId}/ingest`, null, {
    timeout: 600_000,
  })
  return resp.data
}

export interface IngestAllResult {
  total: number
  succeeded: number
  failed: number
  processed: IngestResult[]
  errors: { doc_id: number; error: string }[]
}

export async function ingestAllDocuments(): Promise<IngestAllResult> {
  const resp = await api.post<IngestAllResult>('/api/v1/documents/ingest-all', null, {
    timeout: 1_800_000,
  })
  return resp.data
}

export async function deleteDocument(docId: number): Promise<void> {
  await api.delete(`/api/v1/documents/${docId}`)
}

export interface DocumentChunk {
  chunk_id: string
  page: number
  section: string
  part_number: string
  content: string
}

export interface DocumentChunksResponse {
  doc_id: number
  chip_id: number
  chunk_count: number
  shown: number
  chunks: DocumentChunk[]
}

export async function listDocumentChunks(docId: number, limit = 10): Promise<DocumentChunksResponse> {
  const resp = await api.get<DocumentChunksResponse>(`/api/v1/documents/${docId}/chunks`, {
    params: { limit },
  })
  return resp.data
}

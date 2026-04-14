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

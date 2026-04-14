import api from './client'
import type { DocumentUpload } from '@/types/api'

export async function uploadDocument(file: File): Promise<DocumentUpload> {
  const formData = new FormData()
  formData.append('file', file)
  const resp = await api.post<DocumentUpload>('/api/v1/documents', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return resp.data
}

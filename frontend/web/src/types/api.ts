export interface Chunk {
  chunk_id: string
  doc_id: string
  content: string
  chunk_index: number
  page_number?: number
  section: string
  metadata: Record<string, unknown>
}

export interface RetrievalResult {
  chunks: Chunk[]
  query: string
  total: number
}

export interface QueryRequest {
  query: string
  session_id?: string
  stream?: boolean
}

export interface QueryResponse {
  answer: string
  citations: Chunk[]
  trace_id: string
  session_id: string
}

export interface CompareRequest {
  chips: string[]
  parameters?: string[]
}

export interface CompareResult {
  chips: string[]
  parameters: Record<string, Record<string, string>>
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: { id: string; username: string; role: string }
}

export interface DocumentUpload {
  id: string
  filename: string
  status: string
  task_id?: string
}

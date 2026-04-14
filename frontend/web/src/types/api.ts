// ---- Core data contracts (aligned with src/core/types.py) ----

export interface Chunk {
  chunk_id: string
  doc_id: string
  content: string
  chunk_index: number
  page_number?: number
  section: string
  metadata: Record<string, unknown>
}

/** Citation returned inside QueryResponse.citations[] */
export interface Citation {
  chunk_id: string
  doc_id: string
  content: string
  score: number
  source?: string
  page_number?: number
  metadata?: Record<string, unknown>
}

// ---- Query ----

export interface QueryRequest {
  query: string
  session_id?: string
  top_k?: number
}

export interface QueryResponse {
  answer: string
  citations: Citation[]
  trace_id: string
}

// ---- Compare ----

export interface CompareRequest {
  chips: string[]
  parameters?: string[]
}

export interface CompareResult {
  chips: string[]
  parameters: Record<string, Record<string, string>>
}

// ---- Auth (aligned with src/api/schemas/auth.py::TokenResponse) ----

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

// ---- Documents (aligned with src/api/routers/documents.py) ----

/** Response from POST /api/v1/documents/upload */
export interface DocumentUpload {
  task_id: string
  status: string
  filename: string
  file_size: number
  message: string
}

/** Single document item from GET /api/v1/documents */
export interface DocumentMeta {
  doc_id?: number
  title?: string
  filename?: string
  status: string
  source_url?: string
  file_path?: string
  doc_type?: string
  metadata?: Record<string, unknown>
}

/** Paginated response from GET /api/v1/documents */
export interface DocumentListResponse {
  documents: DocumentMeta[]
  page: number
  per_page: number
  total: number
}

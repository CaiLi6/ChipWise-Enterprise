import { http, HttpResponse } from 'msw'

export const handlers = [
  // Auth: login
  http.post('*/api/v1/auth/login', async ({ request }) => {
    const body = (await request.json()) as { username?: string; password?: string }
    if (body.username === 'testuser' && body.password === 'testpass') {
      return HttpResponse.json({
        access_token: 'mock-jwt-token-12345',
        refresh_token: 'mock-refresh-token-12345',
        token_type: 'bearer',
        expires_in: 3600,
      })
    }
    return new HttpResponse(JSON.stringify({ detail: 'Invalid credentials' }), { status: 401 })
  }),

  // Auth: refresh
  http.post('*/api/v1/auth/refresh', () => {
    return HttpResponse.json({
      access_token: 'mock-jwt-refreshed-token',
      refresh_token: 'mock-refresh-token-new',
      token_type: 'bearer',
      expires_in: 3600,
    })
  }),

  // Query: standard (non-streaming)
  http.post('*/api/v1/query', () => {
    return HttpResponse.json({
      answer: 'STM32F407 的最大主频为 168 MHz，支持 FPU 浮点运算单元。',
      citations: [
        {
          chunk_id: 'chunk-001',
          doc_id: 'doc-stm32f407',
          content: 'The STM32F407 operates at up to 168 MHz with an FPU.',
          score: 0.95,
        },
      ],
      trace_id: 'trace-mock-001',
    })
  }),

  // Documents: list
  http.get('*/api/v1/documents', () => {
    return HttpResponse.json({
      documents: [
        {
          doc_id: 'doc-001',
          filename: 'STM32F407_datasheet.pdf',
          title: 'STM32F407 Datasheet',
          doc_type: 'datasheet',
          status: 'completed',
          created_at: '2026-01-15T10:00:00Z',
        },
        {
          doc_id: 'doc-002',
          filename: 'GD32F303_manual.pdf',
          title: 'GD32F303 Reference Manual',
          doc_type: 'reference_manual',
          status: 'processing',
          created_at: '2026-01-16T14:30:00Z',
        },
      ],
      total: 2,
    })
  }),

  // Documents: upload
  http.post('*/api/v1/documents/upload', () => {
    return HttpResponse.json({
      doc_id: 'doc-new-001',
      filename: 'test-upload.pdf',
      task_id: 'task-mock-001',
    })
  }),

  // Compare
  http.post('*/api/v1/compare', () => {
    return HttpResponse.json({
      chips: ['STM32F407', 'STM32F103'],
      parameters: {
        'Max Frequency': { STM32F407: '168 MHz', STM32F103: '72 MHz' },
        'Flash': { STM32F407: '1 MB', STM32F103: '512 KB' },
        'RAM': { STM32F407: '192 KB', STM32F103: '64 KB' },
        'GPIO': { STM32F407: '140', STM32F103: '80' },
      },
      summary: 'STM32F407 provides significantly higher performance.',
    })
  }),
]

import api from './client'
import type { LoginRequest, LoginResponse } from '@/types/api'

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const resp = await api.post<LoginResponse>('/api/v1/auth/login', data)
  return resp.data
}

export function getSSOLoginURL(provider: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || ''
  return `${base}/api/v1/auth/sso/login?provider=${provider}`
}

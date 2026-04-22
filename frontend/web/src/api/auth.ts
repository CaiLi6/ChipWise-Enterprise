import axios from 'axios'
import api from './client'
import type { LoginRequest, LoginResponse, RegisterRequest } from '@/types/api'

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const resp = await api.post<LoginResponse>('/api/v1/auth/login', data)
  return resp.data
}

export async function register(data: RegisterRequest): Promise<LoginResponse> {
  const resp = await api.post<LoginResponse>('/api/v1/auth/register', data)
  return resp.data
}

/**
 * Refresh the access token. Uses a raw axios instance (NOT the intercepted
 * client) to avoid an infinite 401→refresh→401 loop.
 */
export async function refreshToken(token: string): Promise<LoginResponse> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || ''
  const resp = await axios.post<LoginResponse>(
    `${baseURL}/api/v1/auth/refresh`,
    { refresh_token: token },
  )
  return resp.data
}

export function getSSOLoginURL(provider: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || ''
  return `${base}/api/v1/auth/sso/login?provider=${provider}`
}

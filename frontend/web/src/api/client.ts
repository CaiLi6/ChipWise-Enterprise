import axios from 'axios'
import type { InternalAxiosRequestConfig } from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 60000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('chipwise_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let isRefreshing = false
let pendingRequests: Array<(token: string) => void> = []

// Endpoints where 401/403 means "bad credentials", NOT "expired token" —
// never try to refresh or redirect to /login for these.
const AUTH_NO_RETRY = /\/api\/v1\/auth\/(login|register|refresh)$/

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    const url = original?.url || ''
    if (error.response?.status === 401 && !AUTH_NO_RETRY.test(url) && !original._retry) {
      original._retry = true

      // Lazy import to avoid circular dependency at module load time
      const { useAuthStore } = await import('@/stores/auth')
      const auth = useAuthStore()

      if (!isRefreshing) {
        isRefreshing = true
        try {
          await auth.refresh()
          isRefreshing = false
          // Replay all queued requests
          pendingRequests.forEach((cb) => cb(auth.token))
          pendingRequests = []
          original.headers.Authorization = `Bearer ${auth.token}`
          return api(original)
        } catch {
          isRefreshing = false
          pendingRequests = []
          auth.logout()
          window.location.href = '/login'
          return Promise.reject(error)
        }
      } else {
        // Another refresh is in flight — queue this request
        return new Promise((resolve) => {
          pendingRequests.push((newToken: string) => {
            original.headers.Authorization = `Bearer ${newToken}`
            resolve(api(original))
          })
        })
      }
    }
    return Promise.reject(error)
  },
)

export default api

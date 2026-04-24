import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, refreshToken as apiRefresh } from '@/api/auth'
import type { LoginRequest } from '@/types/api'

// Decode the JWT `exp` claim (seconds since epoch) without verifying signature.
// Returns 0 on any parse failure so callers fall back to "no proactive refresh".
function getTokenExp(token: string): number {
  if (!token) return 0
  try {
    const payload = token.split('.')[1]
    if (!payload) return 0
    // Base64url → base64
    const b64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    const json = atob(b64.padEnd(b64.length + ((4 - (b64.length % 4)) % 4), '='))
    const claims = JSON.parse(json) as { exp?: number }
    return typeof claims.exp === 'number' ? claims.exp : 0
  } catch {
    return 0
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('chipwise_token') || '')
  const refreshTokenValue = ref(localStorage.getItem('chipwise_refresh_token') || '')
  const username = ref(localStorage.getItem('chipwise_user') || '')
  const isLoggedIn = computed(() => !!token.value)

  let refreshTimer: ReturnType<typeof setTimeout> | null = null
  let inflightRefresh: Promise<void> | null = null

  // Refresh `accessToken` ~60s before its `exp` claim. Reschedules itself.
  function scheduleProactiveRefresh() {
    if (refreshTimer) {
      clearTimeout(refreshTimer)
      refreshTimer = null
    }
    const exp = getTokenExp(token.value)
    if (!exp) return
    const nowMs = Date.now()
    const expMs = exp * 1000
    const leadMs = 60_000 // refresh 60s before expiry
    let delay = expMs - nowMs - leadMs
    if (delay < 0) delay = 0
    // Cap at 24h so setTimeout stays safe even with very long TTLs
    if (delay > 24 * 3600 * 1000) delay = 24 * 3600 * 1000
    refreshTimer = setTimeout(() => {
      refresh().catch(() => {
        /* swallow — failing refresh will be handled by next 401 in interceptor */
      })
    }, delay)
  }

  async function login(data: LoginRequest) {
    const resp = await apiLogin(data)
    token.value = resp.access_token
    refreshTokenValue.value = resp.refresh_token
    username.value = data.username
    localStorage.setItem('chipwise_token', resp.access_token)
    localStorage.setItem('chipwise_refresh_token', resp.refresh_token)
    localStorage.setItem('chipwise_user', data.username)
    scheduleProactiveRefresh()
  }

  async function refresh(): Promise<void> {
    // Coalesce concurrent refresh calls so SSE + axios + scheduler don't stampede
    if (inflightRefresh) return inflightRefresh
    if (!refreshTokenValue.value) throw new Error('No refresh token')
    inflightRefresh = (async () => {
      try {
        const resp = await apiRefresh(refreshTokenValue.value)
        token.value = resp.access_token
        refreshTokenValue.value = resp.refresh_token
        localStorage.setItem('chipwise_token', resp.access_token)
        localStorage.setItem('chipwise_refresh_token', resp.refresh_token)
        scheduleProactiveRefresh()
      } finally {
        inflightRefresh = null
      }
    })()
    return inflightRefresh
  }

  function logout() {
    if (refreshTimer) {
      clearTimeout(refreshTimer)
      refreshTimer = null
    }
    token.value = ''
    refreshTokenValue.value = ''
    username.value = ''
    localStorage.removeItem('chipwise_token')
    localStorage.removeItem('chipwise_refresh_token')
    localStorage.removeItem('chipwise_user')
  }

  // Kick off proactive refresh on app load if there's already a token in storage.
  if (token.value) scheduleProactiveRefresh()

  return { token, refreshToken: refreshTokenValue, username, isLoggedIn, login, refresh, logout }
})

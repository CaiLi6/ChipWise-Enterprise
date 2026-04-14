import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, refreshToken as apiRefresh } from '@/api/auth'
import type { LoginRequest } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('chipwise_token') || '')
  const refreshTokenValue = ref(localStorage.getItem('chipwise_refresh_token') || '')
  const username = ref(localStorage.getItem('chipwise_user') || '')
  const isLoggedIn = computed(() => !!token.value)

  async function login(data: LoginRequest) {
    const resp = await apiLogin(data)
    token.value = resp.access_token
    refreshTokenValue.value = resp.refresh_token
    username.value = data.username
    localStorage.setItem('chipwise_token', resp.access_token)
    localStorage.setItem('chipwise_refresh_token', resp.refresh_token)
    localStorage.setItem('chipwise_user', data.username)
  }

  async function refresh(): Promise<void> {
    if (!refreshTokenValue.value) throw new Error('No refresh token')
    const resp = await apiRefresh(refreshTokenValue.value)
    token.value = resp.access_token
    refreshTokenValue.value = resp.refresh_token
    localStorage.setItem('chipwise_token', resp.access_token)
    localStorage.setItem('chipwise_refresh_token', resp.refresh_token)
  }

  function logout() {
    token.value = ''
    refreshTokenValue.value = ''
    username.value = ''
    localStorage.removeItem('chipwise_token')
    localStorage.removeItem('chipwise_refresh_token')
    localStorage.removeItem('chipwise_user')
  }

  return { token, refreshToken: refreshTokenValue, username, isLoggedIn, login, refresh, logout }
})

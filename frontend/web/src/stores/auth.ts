import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin } from '@/api/auth'
import type { LoginRequest } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('chipwise_token') || '')
  const username = ref(localStorage.getItem('chipwise_user') || '')
  const isLoggedIn = computed(() => !!token.value)

  async function login(data: LoginRequest) {
    const resp = await apiLogin(data)
    token.value = resp.access_token
    username.value = resp.user.username
    localStorage.setItem('chipwise_token', resp.access_token)
    localStorage.setItem('chipwise_user', resp.user.username)
  }

  function logout() {
    token.value = ''
    username.value = ''
    localStorage.removeItem('chipwise_token')
    localStorage.removeItem('chipwise_user')
  }

  return { token, username, isLoggedIn, login, logout }
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../auth'

// Mock the API module
vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  refreshToken: vi.fn(),
}))

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('starts logged out', () => {
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
    expect(store.token).toBe('')
  })

  it('login stores tokens and username', async () => {
    const { login: mockLogin } = await import('@/api/auth')
    ;(mockLogin as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: 'at-123',
      refresh_token: 'rt-456',
      token_type: 'bearer',
      expires_in: 3600,
    })

    const store = useAuthStore()
    await store.login({ username: 'alice', password: 'pass' })

    expect(store.isLoggedIn).toBe(true)
    expect(store.token).toBe('at-123')
    expect(store.refreshToken).toBe('rt-456')
    expect(store.username).toBe('alice')
    expect(localStorage.getItem('chipwise_token')).toBe('at-123')
    expect(localStorage.getItem('chipwise_refresh_token')).toBe('rt-456')
  })

  it('logout clears all state', async () => {
    const store = useAuthStore()
    // Simulate logged-in state
    localStorage.setItem('chipwise_token', 'at')
    localStorage.setItem('chipwise_refresh_token', 'rt')
    localStorage.setItem('chipwise_user', 'bob')

    store.logout()

    expect(store.isLoggedIn).toBe(false)
    expect(store.token).toBe('')
    expect(store.refreshToken).toBe('')
    expect(localStorage.getItem('chipwise_token')).toBeNull()
  })

  it('refresh updates access token', async () => {
    const { refreshToken: mockRefresh } = await import('@/api/auth')
    ;(mockRefresh as ReturnType<typeof vi.fn>).mockResolvedValue({
      access_token: 'at-new',
      refresh_token: 'rt-new',
      token_type: 'bearer',
      expires_in: 3600,
    })

    const store = useAuthStore()
    // Simulate having a refresh token
    store.$patch({ refreshToken: 'rt-old', token: 'at-old' })
    localStorage.setItem('chipwise_refresh_token', 'rt-old')

    await store.refresh()

    expect(store.token).toBe('at-new')
    expect(store.refreshToken).toBe('rt-new')
  })

  it('refresh throws when no refresh token', async () => {
    const store = useAuthStore()
    await expect(store.refresh()).rejects.toThrow('No refresh token')
  })
})

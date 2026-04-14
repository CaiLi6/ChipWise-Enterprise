import { test, expect } from '@playwright/test'

test.describe('Auth Guard', () => {
  test('redirects to /login when not authenticated', async ({ page }) => {
    // Clear auth state
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.removeItem('chipwise_token')
      localStorage.removeItem('chipwise_refresh_token')
      localStorage.removeItem('chipwise_user')
    })

    // Try to access protected route
    await page.goto('/query')

    // Should redirect to login with ?redirect=/query
    await expect(page).toHaveURL(/\/login/)
    const url = page.url()
    expect(url).toContain('redirect')
  })

  test('authenticated user can access /query directly', async ({ page }) => {
    // Set auth token
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.setItem('chipwise_token', 'mock-token')
      localStorage.setItem('chipwise_refresh_token', 'mock-refresh')
      localStorage.setItem('chipwise_user', 'testuser')
    })

    await page.goto('/query')
    await expect(page).toHaveURL(/\/query/)
    await expect(page.locator('text=智能查询')).toBeVisible()
  })

  test('logged-in user visiting /login gets redirected to /', async ({ page }) => {
    // Set auth token
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.setItem('chipwise_token', 'mock-token')
      localStorage.setItem('chipwise_refresh_token', 'mock-refresh')
      localStorage.setItem('chipwise_user', 'testuser')
    })

    await page.goto('/login')
    // Should redirect away from login
    await expect(page).not.toHaveURL(/\/login/)
  })
})

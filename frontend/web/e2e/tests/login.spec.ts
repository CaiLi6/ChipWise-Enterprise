import { test, expect } from '@playwright/test'

test.describe('Login Page', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any auth state
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.removeItem('chipwise_token')
      localStorage.removeItem('chipwise_refresh_token')
      localStorage.removeItem('chipwise_user')
    })
    await page.reload()
  })

  test('shows login form with required fields', async ({ page }) => {
    await expect(page.locator('text=ChipWise Enterprise')).toBeVisible()
    await expect(page.locator('input[placeholder="用户名"]')).toBeVisible()
    await expect(page.locator('input[placeholder="密码"]')).toBeVisible()
    await expect(page.locator('button:has-text("登录")')).toBeVisible()
  })

  test('successful login redirects to /query', async ({ page }) => {
    // Mock the login API
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-token',
          refresh_token: 'mock-refresh',
          token_type: 'bearer',
          expires_in: 3600,
        }),
      })
    })

    await page.fill('input[placeholder="用户名"]', 'testuser')
    await page.fill('input[placeholder="密码"]', 'testpass')
    await page.click('button:has-text("登录")')

    // Should navigate to /query after login
    await expect(page).toHaveURL(/\/query/)
  })

  test('failed login shows error message', async ({ page }) => {
    // Mock the login API to return 401
    await page.route('**/api/v1/auth/login', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid credentials' }),
      })
    })

    await page.fill('input[placeholder="用户名"]', 'wrong')
    await page.fill('input[placeholder="密码"]', 'wrong')
    await page.click('button:has-text("登录")')

    await expect(page.locator('text=登录失败')).toBeVisible({ timeout: 5000 })
  })

  test('SSO buttons are visible', async ({ page }) => {
    await expect(page.locator('button:has-text("Keycloak")')).toBeVisible()
    await expect(page.locator('button:has-text("钉钉")')).toBeVisible()
    await expect(page.locator('button:has-text("飞书")')).toBeVisible()
  })
})

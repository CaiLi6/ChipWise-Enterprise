import { test, expect } from '@playwright/test'

test.describe('Query Page', () => {
  test.beforeEach(async ({ page }) => {
    // Set auth token to bypass login guard
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.setItem('chipwise_token', 'mock-token')
      localStorage.setItem('chipwise_refresh_token', 'mock-refresh')
      localStorage.setItem('chipwise_user', 'testuser')
    })

    // Mock query API
    await page.route('**/api/v1/query', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer: 'STM32F407 的最大主频为 168 MHz。',
          citations: [
            {
              chunk_id: 'chunk-001',
              doc_id: 'doc-stm32f407',
              content: 'The STM32F407 operates at up to 168 MHz.',
              score: 0.95,
            },
          ],
          trace_id: 'trace-001',
        }),
      })
    })

    await page.goto('/query')
  })

  test('shows welcome message when empty', async ({ page }) => {
    await expect(page.locator('text=欢迎使用 ChipWise 智能查询')).toBeVisible()
  })

  test('can send a message and receive response', async ({ page }) => {
    const input = page.locator('input[placeholder="输入芯片查询问题..."]')
    await input.fill('STM32F407 的最大主频是多少？')
    await input.press('Enter')

    // User message should appear
    await expect(page.locator('text=STM32F407 的最大主频是多少？')).toBeVisible()
  })
})

import { test, expect } from '@playwright/test'

test.describe('Compare Page', () => {
  test.beforeEach(async ({ page }) => {
    // Set auth token
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.setItem('chipwise_token', 'mock-token')
      localStorage.setItem('chipwise_refresh_token', 'mock-refresh')
      localStorage.setItem('chipwise_user', 'testuser')
    })

    // Mock compare API
    await page.route('**/api/v1/compare', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          chips: ['STM32F407', 'STM32F103'],
          parameters: {
            'Max Frequency': { STM32F407: '168 MHz', STM32F103: '72 MHz' },
            'Flash': { STM32F407: '1 MB', STM32F103: '512 KB' },
            'RAM': { STM32F407: '192 KB', STM32F103: '64 KB' },
          },
          summary: 'STM32F407 provides higher performance.',
        }),
      })
    })

    await page.goto('/compare')
  })

  test('shows chip select and compare button', async ({ page }) => {
    await expect(page.locator('text=芯片对比')).toBeVisible()
    await expect(page.locator('button:has-text("对比")')).toBeVisible()
  })

  test('clicking compare shows results table', async ({ page }) => {
    await page.click('button:has-text("对比")')

    // Table should appear with parameter rows
    await expect(page.locator('text=Max Frequency')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('text=168 MHz')).toBeVisible()
    await expect(page.locator('text=72 MHz')).toBeVisible()
  })
})

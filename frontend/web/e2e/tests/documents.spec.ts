import { test, expect } from '@playwright/test'

test.describe('Documents Page', () => {
  test.beforeEach(async ({ page }) => {
    // Set auth token
    await page.goto('/login')
    await page.evaluate(() => {
      localStorage.setItem('chipwise_token', 'mock-token')
      localStorage.setItem('chipwise_refresh_token', 'mock-refresh')
      localStorage.setItem('chipwise_user', 'testuser')
    })

    // Mock documents list API
    await page.route('**/api/v1/documents', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            documents: [
              {
                doc_id: 'doc-001',
                filename: 'STM32F407_datasheet.pdf',
                title: 'STM32F407 Datasheet',
                doc_type: 'datasheet',
                status: 'completed',
                created_at: '2026-01-15T10:00:00Z',
              },
            ],
            total: 1,
          }),
        })
      }
    })

    // Mock upload API
    await page.route('**/api/v1/documents/upload', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          doc_id: 'doc-new',
          filename: 'uploaded.pdf',
          task_id: 'task-001',
        }),
      })
    })

    await page.goto('/documents')
  })

  test('shows document list', async ({ page }) => {
    await expect(page.locator('text=文档管理')).toBeVisible()
    await expect(page.locator('text=STM32F407_datasheet.pdf')).toBeVisible({ timeout: 5000 })
  })

  test('shows upload button', async ({ page }) => {
    await expect(page.locator('button:has-text("上传文档")')).toBeVisible()
  })

  test('shows document status tag', async ({ page }) => {
    await expect(page.locator('text=completed')).toBeVisible({ timeout: 5000 })
  })
})

// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('EDBotv8 API Health', () => {
  test('health endpoint should be accessible', async ({ page }) => {
    await page.goto('/health');
    
    // Should return JSON health status
    const response = await page.waitForResponse('**/health');
    expect(response.status()).toBe(200);
    
    const healthData = await response.json();
    expect(healthData).toHaveProperty('status');
    expect(healthData.status).toBe('healthy');
  });

  test('API documentation should be accessible', async ({ page }) => {
    await page.goto('/docs');
    
    // Should load Swagger UI
    await expect(page.locator('.swagger-ui')).toBeVisible();
    await expect(page.locator('text=EDBotv8 API')).toBeVisible();
  });

  test('metrics endpoint should be accessible', async ({ page }) => {
    await page.goto('/metrics');
    
    // Should return Prometheus metrics
    const content = await page.textContent('body');
    expect(content).toContain('# HELP');
    expect(content).toContain('# TYPE');
  });
});
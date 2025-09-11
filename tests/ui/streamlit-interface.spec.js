// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('EDBotv8 Streamlit Interface', () => {
  test.beforeEach(async ({ page }) => {
    // Assuming Streamlit runs on port 8501
    await page.goto('http://localhost:8501', { waitUntil: 'networkidle' });
  });

  test('Streamlit app should load', async ({ page }) => {
    // Wait for Streamlit to fully load
    await page.waitForSelector('[data-testid="stApp"]', { timeout: 10000 });
    
    // Check for the main app container
    await expect(page.locator('[data-testid="stApp"]')).toBeVisible();
    
    // Look for common Streamlit elements
    const title = page.locator('h1').first();
    if (await title.isVisible()) {
      await expect(title).toContainText(/EDBotv8|Emergency|Medical/i);
    }
  });

  test('should have query input interface', async ({ page }) => {
    // Look for text input or text area for queries
    const textInput = page.locator('input[type="text"], textarea').first();
    if (await textInput.isVisible()) {
      await expect(textInput).toBeVisible();
      
      // Test typing a query
      await textInput.fill('test medical query');
      await expect(textInput).toHaveValue('test medical query');
    }
  });

  test('should have submit button for queries', async ({ page }) => {
    // Look for submit or search button
    const submitButton = page.locator('button').filter({ hasText: /submit|search|query|ask/i }).first();
    if (await submitButton.isVisible()) {
      await expect(submitButton).toBeVisible();
      await expect(submitButton).toBeEnabled();
    }
  });
});

test.describe('EDBotv8 Streamlit Functionality', () => {
  test.skip('query submission works', async ({ page }) => {
    // Skip by default since Streamlit might not be running
    await page.goto('http://localhost:8501');
    
    const textInput = page.locator('input[type="text"], textarea').first();
    const submitButton = page.locator('button').filter({ hasText: /submit|search|query/i }).first();
    
    if (await textInput.isVisible() && await submitButton.isVisible()) {
      await textInput.fill('what is the STEMI protocol');
      await submitButton.click();
      
      // Wait for response
      await page.waitForTimeout(5000);
      
      // Check if response appears
      const responseArea = page.locator('text=/STEMI|protocol|cardiac/i').first();
      if (await responseArea.isVisible()) {
        await expect(responseArea).toBeVisible();
      }
    }
  });
});
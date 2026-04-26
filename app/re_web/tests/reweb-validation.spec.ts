import { expect, test } from '@playwright/test';

const baseURL = process.env.REWEB_BASE_URL ?? 'http://127.0.0.1:18080';

test('React web UI routes, theme persistence, and backtest autosave', async ({ page }) => {
  test.setTimeout(90000);
  const originalSettings = await page.request.get(`${baseURL}/api/settings`).then((response) => response.json());

  try {
    await page.goto(`${baseURL}/app`);
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Recent Runs')).toBeVisible();

    await page.getByLabel('Toggle theme').click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');

    await page.getByRole('link', { name: /Backtest/ }).click();
    await expect(page.getByRole('heading', { name: 'Backtest' })).toBeVisible();
    const pairsField = page.getByLabel('Pairs');
    const autosavePairs = `BTC/USDT, ETH/USDT, TEST${Date.now()}/USDT`;
    await pairsField.fill(autosavePairs);
    await expect(page.locator('.state-saved')).toBeVisible({ timeout: 4000 });
    await expect
      .poll(async () => {
        const response = await page.request.get(`${baseURL}/api/settings`);
        const settings = await response.json();
        return settings.backtest_preferences.default_pairs;
      })
      .toBe(autosavePairs);

    await page.goto(`${baseURL}/app/optimizer`);
    await expect(page.getByRole('heading', { name: 'Optimizer' })).toBeVisible();

    await page.goto(`${baseURL}/app/run`);
    await expect(page.getByRole('heading', { name: 'Run Detail' })).toBeVisible();

    await page.goto(`${baseURL}/app/comparison`);
    await expect(page.getByRole('heading', { name: 'Comparison' })).toBeVisible();

    await page.goto(`${baseURL}/app/settings`);
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${baseURL}/app/backtest`);
    await expect(page.getByRole('heading', { name: 'Backtest' })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(overflow).toBe(false);
  } finally {
    await page.request.put(`${baseURL}/api/settings`, { data: originalSettings });
  }
});

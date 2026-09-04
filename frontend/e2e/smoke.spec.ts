import { expect, test } from '@playwright/test';

/**
 * Backend-free smoke suite (E2E matrix rows 1-form, 8-form, 20, plus the
 * responsive overflow guard). These run wherever the dev server can start:
 * no API, no seeded users required.
 */

test.describe('public site', () => {
  test('landing renders hero, navigation, and CTAs', async ({ page }) => {
    await page.goto('/');
    await expect(
      page.getByRole('heading', { level: 1, name: /Research, backtest, and monitor dYdX trading bots/i })
    ).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sign in' }).first()).toBeVisible();
    await expect(page.getByRole('link', { name: 'Request access' }).first()).toBeVisible();
  });

  test('pricing renders with a single h1 and no horizontal overflow at 375px', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/pricing');
    await expect(page.locator('h1')).toHaveCount(1);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test('unknown route lands on a routable page, not a blank screen', async ({ page }) => {
    await page.goto('/definitely-not-a-real-route');
    // Unauthenticated users get forwarded to /login by the auth gate.
    await expect(page).toHaveURL(/\/(login|unauthorized)/);
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  });
});

test.describe('login form mechanics', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('submit stays disabled until both fields are filled', async ({ page }) => {
    const submit = page.getByRole('button', { name: 'Sign in' });
    await expect(submit).toBeDisabled();

    await page.getByRole('textbox', { name: 'Username or email' }).fill('someone');
    await expect(submit).toBeDisabled();

    await page.getByRole('textbox', { name: 'Password' }).fill('some-password');
    await expect(submit).toBeEnabled();
  });

  test('password visibility toggle switches input type', async ({ page }) => {
    const password = page.getByRole('textbox', { name: 'Password' });
    await password.fill('secret-value');
    await expect(password).toHaveAttribute('type', 'password');

    await page.getByRole('button', { name: 'Show password' }).click();
    await expect(password).toHaveAttribute('type', 'text');
  });

  test('login page has no horizontal overflow at 320px', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 690 });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test.describe('protected workspace boundary', () => {
  test('unauthenticated /dashboard visit redirects to login', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  });
});

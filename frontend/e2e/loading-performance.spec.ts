import { expect, signIn, test } from './fixtures';

const WORKSPACE_PATHS = ['/api/v1/products', '/api/v1/decisions',
  '/api/v1/watchlists/default/items', '/api/v1/quotes'];

test.describe('time to usable workspace content', () => {
  test('measures a fresh guest visit without assuming a twelve-second delay', async ({ page }) => {
    const started = performance.now();
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Follow the evidence/ })).toBeVisible();
    const usableMs = performance.now() - started;
    console.log(`[performance] fresh guest usable content: ${usableMs.toFixed(1)} ms`);
    test.info().annotations.push({ type:'guest-usable-ms', description:usableMs.toFixed(1) });
    expect(usableMs).toBeLessThan(5_000);
    await expect(page.getByText(/Products under investigation/)).toBeVisible();
  });

  test('measures auth bootstrap and verifies workspace reads fan out in parallel', async ({ page }) => {
    await signIn(page, 'Performance workspace');
    const requests: { path:string; start:number; end?:number }[] = [];
    page.on('request', request => {
      const path = new URL(request.url()).pathname;
      if (path === '/api/v1/auth/me' || WORKSPACE_PATHS.includes(path))
        requests.push({ path, start:performance.now() });
    });
    page.on('response', response => {
      const path = new URL(response.url()).pathname;
      const open = [...requests].reverse().find(item => item.path === path && item.end === undefined);
      if (open) open.end = performance.now();
    });
    const started = performance.now();
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Follow the evidence/ })).toBeVisible();
    await expect.poll(() => requests.filter(item => WORKSPACE_PATHS.includes(item.path) && item.end).length).toBe(4);
    const usableMs = performance.now() - started;
    const me = requests.find(item => item.path === '/api/v1/auth/me');
    const workspace = requests.filter(item => WORKSPACE_PATHS.includes(item.path));
    expect(me?.end).toBeDefined();
    expect(workspace).toHaveLength(4);
    expect(Math.min(...workspace.map(item => item.start))).toBeGreaterThanOrEqual((me?.end ?? 0) - 5);
    expect(Math.max(...workspace.map(item => item.start)) - Math.min(...workspace.map(item => item.start))).toBeLessThan(250);
    expect(usableMs).toBeLessThan(5_000);
    console.log(`[performance] authenticated usable content: ${usableMs.toFixed(1)} ms; workspace request start spread: ${(Math.max(...workspace.map(item => item.start)) - Math.min(...workspace.map(item => item.start))).toFixed(1)} ms`);
    test.info().annotations.push({ type:'authenticated-usable-ms', description:usableMs.toFixed(1) });
  });

  test('measures usable client-side page navigation', async ({ page }) => {
    await signIn(page, 'Navigation performance workspace');
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Follow the evidence/ })).toBeVisible();
    const started = performance.now();
    await page.getByRole('navigation', { name:'Main navigation' })
      .getByRole('link', { name:/Product X-Ray/ }).click();
    await expect(page.getByRole('heading', { name: 'Put a product under the X-Ray.' })).toBeVisible();
    const usableMs = performance.now() - started;
    console.log(`[performance] client-side navigation usable content: ${usableMs.toFixed(1)} ms`);
    test.info().annotations.push({ type:'navigation-usable-ms', description:usableMs.toFixed(1) });
    expect(usableMs).toBeLessThan(3_000);
  });
});

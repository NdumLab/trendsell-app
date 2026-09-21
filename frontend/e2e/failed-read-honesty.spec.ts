import { apiProduct, asin, expect, recordFullCoverage, test } from './fixtures';

/** A failed read must never be presented as a fact about the workspace.
 *
 *  This is the F03 defect class, found on three further screens during the end-to-end
 *  review: Decision Room was corrected, but Today, the evidence ledger and the product
 *  picker still render an unavailable read as an affirmative negative — "00", "No
 *  evidence recorded yet", "No products yet." Each case below records real data first,
 *  then fails only the one request that would report it.
 */

test('the dashboard does not report a failed summary as an empty workspace', async ({ page, workspace }) => {
  const productId = await apiProduct(page, asin(81), 'Dashboard counter candidate');
  await recordFullCoverage(page, productId);

  await page.route('**/api/v1/summary', route => route.fulfill({
    status: 503, contentType: 'application/json',
    body: JSON.stringify({ detail: 'Summary temporarily unavailable' }),
  }));
  await page.goto('/');

  // The product grid on the same screen reads from a different request and shows the
  // product, so the screen contradicts itself.
  await expect(page.getByText('Dashboard counter candidate')).toBeVisible();
  // Assert the honest state positively first, so this cannot pass by checking too early.
  await expect(page.getByText(/counts could not be loaded/)).toBeVisible();
  const counter = page.locator('.summary-card', { hasText: 'Products under investigation' });
  await expect(counter).toContainText('--');
  await expect(counter).not.toContainText('00');
  expect(workspace.workspace).toBe('E2E workspace');
});

test('a failed evidence read is not reported as "no evidence recorded"', async ({ page, workspace }) => {
  const productId = await apiProduct(page, asin(82), 'Evidence ledger candidate');
  await recordFullCoverage(page, productId);   // four real records exist

  await page.route(`**/api/v1/products/${productId}/evidence`, route => route.fulfill({
    status: 503, contentType: 'application/json',
    body: JSON.stringify({ detail: 'Evidence read temporarily unavailable' }),
  }));
  await page.goto(`/products/${productId}`);
  await page.getByRole('button', { name: 'Evidence ledger' }).click();

  await expect(page.getByText(/evidence records could not be loaded/)).toBeVisible();
  await expect(page.getByText('No evidence recorded yet')).toHaveCount(0);
  expect(workspace.workspace).toBe('E2E workspace');
});

test('a failed product search is not reported as "no product matches"', async ({ page, workspace }) => {
  await apiProduct(page, asin(83), 'Picker candidate');

  // Let the screen load normally first, so the picker really renders, then fail only the
  // search request the picker issues for a typed term.
  await page.goto('/suppliers');
  await page.getByRole('button', { name: 'Add a quote' }).click();
  await expect(page.getByLabel('Search your products')).toBeVisible();

  // A predicate, not a glob: Playwright treats "?" in a glob as a single-character wildcard.
  await page.route(url => url.pathname === '/api/v1/products' && url.searchParams.has('search'),
    route => route.fulfill({
      status: 503, contentType: 'application/json',
      body: JSON.stringify({ detail: 'Product search temporarily unavailable' }),
    }));
  await page.getByLabel('Search your products').fill('Picker');

  await expect(page.getByText(/products could not be loaded/)).toBeVisible();
  await expect(page.getByText('No product matches that search.')).toHaveCount(0);
  expect(workspace.workspace).toBe('E2E workspace');
});

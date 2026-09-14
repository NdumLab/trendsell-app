import { test, expect, apiProduct, asin } from './fixtures';

/** Growing lists and product pickers, past the page that happens to be loaded.
 *
 *  Review finding R10: quotes and watches fetched a flat first 200 records with no
 *  next-page control, so their totals could promise more than the screen could ever show;
 *  the supplier product picker chose from the loaded product page (50), so an older
 *  product could not be quoted; and Discover's search lived in workspace state, so it kept
 *  narrowing the product list after the user had navigated away.
 *
 *  These seed real records through the API — the disposable stack in playwright.config.ts,
 *  never a real workspace — because the defect only appears past a page boundary.
 */

// Seeding several hundred records over HTTP is the slow part, not the assertions.
test.setTimeout(180_000);

const PAGE = 50;

/** Run `work` over `count` items, a few at a time: 250 sequential round trips is the
 *  difference between a fast test and a flaky one. */
async function seed(count: number, work: (index: number) => Promise<void>, concurrency = 16) {
  for (let start = 0; start < count; start += concurrency)
    await Promise.all(Array.from({ length: Math.min(concurrency, count - start) },
                                 (_, offset) => work(start + offset)));
}

test('a quote room past the old flat limit can be paged to the end', async ({ page, workspace }) => {
  const product = await apiProduct(page, asin(1), 'Quoted product');
  const TOTAL = 250;
  await seed(TOTAL, async index => {
    const response = await page.request.post('/api/v1/quotes', {
      headers: { 'X-Requested-With': 'TrendSell' },
      data: { product_id: product, supplier: `Disposable supplier ${index}`,
              source_url: 'https://example.test/quote', unit_price_usd: 8.4, moq: 100,
              lead_days: 30, quote_date: '2026-09-01', incoterm: 'FOB', notes: '' },
    });
    expect(response.status(), await response.text()).toBe(201);
  });

  await page.goto('/suppliers');
  // The badge states the true total, so the screen must be able to reach it.
  await expect(page.getByText(String(TOTAL), { exact: true })).toBeVisible();
  await expect(page.getByText(`Showing ${PAGE} of ${TOTAL} quotes.`)).toBeVisible();

  const more = page.getByRole('button', { name: 'Load more' });
  // The old code stopped dead at 200 with no control at all.
  for (let loaded = PAGE; loaded < TOTAL; loaded += PAGE) {
    await more.click();
    await expect(page.getByText(`Showing ${Math.min(loaded + PAGE, TOTAL)} of ${TOTAL} quotes.`)).toBeVisible();
  }
  await expect(more).toHaveCount(0);
  await expect(page.getByRole('cell', { name: `Disposable supplier ${TOTAL - 1}`, exact: false })).toHaveCount(1);
});

test('a watchlist past the old flat limit can be paged to the end', async ({ page, workspace }) => {
  const TOTAL = 210;
  const products: string[] = [];
  await seed(TOTAL, async index => {
    const id = await apiProduct(page, asin(1000 + index), `Watched product ${index}`);
    products.push(id);
    const response = await page.request.post('/api/v1/watchlists/default/items', {
      headers: { 'X-Requested-With': 'TrendSell' },
      data: { product_id: id, threshold_pct: 15 },
    });
    expect(response.status(), await response.text()).toBeLessThan(300);
  });
  expect(products).toHaveLength(TOTAL);

  await page.goto('/watchtower');
  await expect(page.getByText(`Showing ${PAGE} of ${TOTAL} watched products.`)).toBeVisible();
  const more = page.getByRole('button', { name: 'Load more' });
  for (let loaded = PAGE; loaded < TOTAL; loaded += PAGE) {
    await more.click();
    await expect(page.getByText(`Showing ${Math.min(loaded + PAGE, TOTAL)} of ${TOTAL} watched products.`)).toBeVisible();
  }
  await expect(more).toHaveCount(0);
});

test('the oldest product is quotable even though it is not on the loaded page', async ({ page, workspace }) => {
  // Created first, so it sorts last: it is not in the first page the workspace loads.
  const oldest = await apiProduct(page, asin(2000), 'Oldest investigation');
  await seed(PAGE + 5, index => apiProduct(page, asin(2001 + index), `Later product ${index}`).then(() => {}));

  await page.goto('/discover');
  // Confirm the premise: the loaded page really does not contain it, but the workspace does.
  await expect(page.getByRole('link', { name: 'Later product 54' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Oldest investigation' })).toHaveCount(0);

  await page.goto('/suppliers');
  await page.getByRole('button', { name: 'Add a quote' }).click();
  const picker = page.getByRole('combobox', { name: 'Product' });
  await expect(picker).toBeVisible();
  // Not offered until searched for — the picker shows a page, but it can reach the rest.
  await page.getByLabel('Search your products').fill('Oldest investigation');
  await expect(picker.getByRole('option', { name: 'Oldest investigation' })).toBeAttached();

  await picker.selectOption({ label: 'Oldest investigation' });
  await page.getByLabel('Supplier name').fill('Disposable supplier');
  await page.getByLabel('Supplier or quote source URL').fill('https://example.test/quote');
  await page.getByLabel('Unit price', { exact: true }).fill('8.4');
  await page.getByLabel('Minimum order (units)').fill('100');
  await page.getByLabel('Lead time (days)').fill('30');
  await page.getByLabel('Quote date').fill('2026-09-01');
  await page.getByRole('button', { name: /Save quote/ }).click();

  // The quote really was recorded against the product that was not on the loaded page.
  await expect(page.getByRole('cell', { name: 'Disposable supplier', exact: false })).toBeVisible();
  const quotes = await (await page.request.get(`/api/v1/quotes?product_id=${oldest}`)).json();
  expect(quotes.total).toBe(1);
});

test('a search typed on Discover does not follow the user to another screen', async ({ page, workspace }) => {
  await apiProduct(page, asin(3000), 'Findable product');

  // Navigation is by link throughout: `page.goto` reloads the app, which would reset the
  // shared state this test is about and pass whether or not the term was ever scoped.
  await page.goto('/discover');
  await page.getByLabel('Search products').fill('nothing-matches-this-term');
  await expect(page.getByRole('link', { name: 'Findable product' })).toHaveCount(0);

  // The term is Discover's filter. Leaving Discover must leave it behind.
  await page.getByRole('link', { name: 'Suppliers' }).click();
  await page.getByRole('button', { name: 'Add a quote' }).click();
  await expect(page.getByRole('combobox', { name: 'Product' })
                   .getByRole('option', { name: 'Findable product' })).toBeAttached();
  await page.getByRole('button', { name: 'Close dialog' }).click();

  await page.getByRole('link', { name: 'Discover' }).click();
  await expect(page.getByRole('link', { name: 'Findable product' })).toBeVisible();
});

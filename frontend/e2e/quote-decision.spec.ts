import { apiProduct, asin, downloadJson, expect, fillDecisionInputs, recordEvidence, test } from './fixtures';

test.describe('quote-to-decision provenance', () => {
  test('a dated quote populates the economics and remains in the saved export', async ({ page, workspace }) => {
    const productId = await apiProduct(page, asin(81), 'Quote-linked candidate');
    const quoteDate = new Date(Date.now() - 2 * 86_400_000).toISOString().slice(0, 10);
    const response = await page.request.post('/api/v1/quotes', {
      headers: { 'X-Requested-With': 'TrendSell' },
      data: { product_id: productId, supplier: 'Controlled supplier fixture',
        source_url: 'https://supplier.example.test/quotes/81', unit_price: 8.4,
        currency: 'USD', moq: 240, lead_days: 21, quote_date: quoteDate,
        incoterm: 'FOB', notes: 'Controlled browser-test quote.' },
    });
    expect(response.status(), await response.text()).toBe(201);
    const quote = await response.json();
    await recordEvidence(page, productId, 'Search interest', 'US', 'Controlled search fixture');

    await page.goto(`/decisions?product=${productId}`);
    await page.getByLabel('Use a saved quote').selectOption(quote.id);
    await expect(page.getByLabel('Order quantity', { exact: true })).toHaveValue('240');
    await expect(page.getByLabel('Supplier unit quote', { exact: true })).toHaveValue('8.4');
    await expect(page.getByText(new RegExp(`MOQ 240.*FOB.*${quoteDate}`))).toBeVisible();
    await fillDecisionInputs(page, { 'Order quantity':'240', 'Supplier unit quote':'8.4' });
    await expect(page.getByText('Base net margin after allocated launch costs')).toBeVisible();
    await expect(page.getByText('Base contribution margin')).toHaveCount(0);
    await page.getByRole('button', { name: 'Save this decision' }).click();
    await expect(page.getByText(/That assessment is immutable/)).toBeVisible();
    const exported = await downloadJson(page, () =>
      page.getByRole('button', { name: 'Export saved assessment' }).click());
    expect(exported.body.supplier_quote.id).toBe(quote.id);
    expect(exported.body.supplier_quote.unit_price).toBe(8.4);
    expect(exported.body.supplier_quote.currency).toBe('USD');
    expect(exported.body.supplier_quote.quote_date).toBe(quoteDate);
    expect(exported.body.assessment.inputs.quantity).toBe(240);
    expect(exported.body.assessment.inputs.unit_cost_usd).toBe(8.4);
    expect(workspace.workspace).toBe('E2E workspace');
  });
});

test.describe('product sales-driver evidence', () => {
  test('shows dated signals separately from causal attribution', async ({ page, workspace }) => {
    const productId = await apiProduct(page, asin(82), 'Driver evidence candidate');
    await recordEvidence(page, productId, 'Advertising activity', 'US', 'Public ad library fixture');
    await recordEvidence(page, productId, 'Creator activity', 'US', 'Creator post fixture');
    await recordEvidence(page, productId, 'Search interest', 'US', 'Search export fixture');
    await recordEvidence(page, productId, 'Marketplace rank', 'US', 'Marketplace fixture');
    await page.goto(`/products/${productId}`);
    await expect(page.getByRole('heading', { name: 'Signals associated with demand' })).toBeVisible();
    for (const heading of ['Advertising', 'Creators', 'Search', 'Marketplace'])
      await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await expect(page.getByText('Association is not attribution.')).toBeVisible();
    await expect(page.getByText(/does not invent competitor revenue/)).toBeVisible();
    expect(workspace.workspace).toBe('E2E workspace');
  });
});

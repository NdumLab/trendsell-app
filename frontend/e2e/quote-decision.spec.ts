import { apiProduct, asin, downloadJson, expect, fillDecisionInputs, recordEvidence, test } from './fixtures';

test.describe('quote-to-decision provenance', () => {
  test('a dated quote populates the economics and remains in the saved export', async ({ page, workspace }) => {
    const productId = await apiProduct(page, asin(81), 'Quote-linked candidate');
    const quoteDate = new Date(Date.now() - 2 * 86_400_000).toISOString().slice(0, 10);
    const validUntil = new Date(Date.now() + 28 * 86_400_000).toISOString().slice(0, 10);
    const response = await page.request.post('/api/v1/quotes', {
      headers: { 'X-Requested-With': 'TrendSell' },
      data: { product_id: productId, supplier: 'Controlled supplier fixture',
        source_url: 'https://supplier.example.test/quotes/81', unit_price: 8.4,
        currency: 'USD', moq: 240, lead_days: 21, quote_date: quoteDate,
        valid_until: validUntil, incoterm: 'CIF',
        product_specifications: '1500 W, 220 V controlled fixture',
        payment_terms: '30% deposit; 70% before shipment',
        delivery_scope: 'international_freight',
        included_costs: ['international_freight', 'insurance'],
        notes: 'Controlled browser-test quote.' },
    });
    expect(response.status(), await response.text()).toBe(201);
    const quote = await response.json();
    await recordEvidence(page, productId, 'Search interest', 'US', 'Controlled search fixture');

    await page.goto(`/decisions?product=${productId}`);
    await page.getByLabel('Use a saved quote').selectOption(quote.id);
    await expect(page.getByLabel('Order quantity', { exact: true })).toHaveValue('240');
    await expect(page.getByLabel('Supplier unit quote', { exact: true })).toHaveValue('8.4');
    await expect(page.getByText(new RegExp(`MOQ 240.*CIF.*${quoteDate}`))).toBeVisible();
    await expect(page.getByLabel('Total international freight', { exact: true })).toBeDisabled();
    await expect(page.getByLabel('Total cargo insurance', { exact: true })).toBeDisabled();
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
    expect(exported.body.supplier_quote.valid_until).toBe(validUntil);
    expect(exported.body.quote_checks.validity_state).toBe('current');
    expect(exported.body.quote_checks.quantity_state).toBe('meets_moq');
    expect(exported.body.quote_checks.cost_inclusions.declared_included).toEqual(['international_freight', 'insurance']);
    expect(exported.body.assessment.inputs.freight_ngn).toBe(0);
    expect(exported.body.assessment.inputs.insurance_ngn).toBe(0);
    expect(exported.body.assessment.inputs.quantity).toBe(240);
    expect(exported.body.assessment.inputs.unit_cost_usd).toBe(8.4);
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('revises a quote without replacing version one and selects the intended revision', async ({ page, workspace }) => {
    const productId = await apiProduct(page, asin(83), 'Versioned quote candidate');
    const quoteDate = new Date(Date.now() - 2 * 86_400_000).toISOString().slice(0, 10);
    const validUntil = new Date(Date.now() + 28 * 86_400_000).toISOString().slice(0, 10);
    const created = await page.request.post('/api/v1/quotes', {
      headers: { 'X-Requested-With': 'TrendSell' },
      data: { product_id: productId, supplier: 'Revision fixture supplier',
        source_url: 'https://supplier.example.test/quotes/83-v1', unit_price: 8.4,
        currency: 'USD', moq: 240, lead_days: 21, quote_date: quoteDate,
        valid_until: validUntil, incoterm: 'FOB',
        product_specifications: '1500 W, 220 V revision fixture',
        payment_terms: '30% deposit; 70% before shipment',
        delivery_scope: 'factory_only', notes: 'Version one.' },
    });
    expect(created.status(), await created.text()).toBe(201);

    await page.goto('/suppliers');
    const firstRow = page.getByRole('row').filter({ hasText: 'Revision fixture supplier' });
    await firstRow.getByRole('button', { name: 'Revise' }).click();
    await expect(page.getByRole('heading', { name: 'Record a revised quote' })).toBeVisible();
    await expect(page.getByLabel('Supplier name')).toHaveAttribute('readonly', '');
    await page.getByLabel('Unit price').fill('7.95');
    await page.getByLabel('Lead time (days)').fill('18');
    await page.getByLabel('Payment terms').fill('20% deposit; 80% before shipment');
    await page.getByLabel('Notes').fill('Version two.');
    await page.getByRole('button', { name: 'Save revised quote' }).click();

    await expect(page.getByText('Revision 1', { exact: true })).toBeVisible();
    await expect(page.getByText('Revision 2', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Revise' })).toHaveCount(1);
    await expect(page.getByText('Superseded', { exact: true })).toBeVisible();
    await page.goto(`/decisions?product=${productId}`);
    const selector = page.getByLabel('Use a saved quote');
    await expect(selector.locator('option')).toHaveCount(3);
    const revisionId = await selector.locator('option')
      .filter({ hasText: 'revision 2 · 7.95 USD' }).getAttribute('value');
    expect(revisionId).not.toBeNull();
    await selector.selectOption(revisionId!);
    await expect(page.getByLabel('Supplier unit quote', { exact: true })).toHaveValue('7.95');
    await expect(page.getByText(/revision 2\. Valid until/)).toBeVisible();
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

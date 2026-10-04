import { asin, captureAndConfirm, enterDemo, expect, fillDecisionInputs, inviteReviewer, test } from './fixtures';

/** Recording evidence and requesting an import-readiness review (E06, N02, N03, D03).
 *
 *  Both were blockers the app used to state without offering any way to resolve them. */
test.describe('evidence and import readiness', () => {
  test('a recorded observation is stored as user input and moves the coverage score', async ({ page, workspace }) => {
    const name = 'Evidence candidate';
    await captureAndConfirm(page, asin(51), name);
    await page.goto('/discover');
    await page.getByRole('link', { name: new RegExp(name) }).click();

    await page.getByRole('button', { name: 'Evidence ledger' }).click();
    await expect(page.getByText('No evidence recorded yet')).toBeVisible();

    await page.getByRole('button', { name: 'Record your first observation' }).click();
    const form = page.getByRole('dialog');
    await form.getByLabel('What did you measure?').selectOption('Search interest');
    await form.getByLabel('Market', { exact: true }).selectOption('US');
    await form.getByLabel('Value').fill('68');
    await form.getByLabel('Unit').fill('index / 100');
    await form.getByLabel('Date observed').fill(new Date(Date.now() - 3 * 86_400_000).toISOString().slice(0, 10));
    await form.getByLabel('Source', { exact: true }).fill('Search trends export');
    await form.getByLabel('How did you read it?').fill('Exported the 12-month series and read the latest weekly point.');
    await form.getByRole('button', { name: 'Record evidence' }).click();
    await expect(form).toBeHidden();

    // A typed number is user input, never an observation.
    const row = page.locator('tbody tr').filter({ hasText: 'Search interest' });
    await expect(row).toBeVisible();
    await expect(row.getByText('User input')).toBeVisible();

    await page.getByRole('button', { name: 'Local viability' }).click();
    await expect(page.getByText('Independent demand metrics')).toBeVisible();
    await expect(page.getByText(/Not a probability of success/)).toBeVisible();
    // Destination evidence is still missing, and the app says so rather than scoring it.
    await expect(page.getByText(/Missing local listings are not low competition/).first()).toBeVisible();
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('an analyst can request an import-readiness review but cannot decide it', async ({ page, workspace }) => {
    const name = 'Review candidate';
    await captureAndConfirm(page, asin(52), name);
    await page.goto('/discover');
    await page.getByRole('link', { name: new RegExp(name) }).click();
    await page.getByRole('button', { name: 'Local viability' }).click();

    await expect(page.getByText('Not reviewed')).toBeVisible();
    await page.getByRole('button', { name: 'Request a review' }).click();
    const form = page.getByRole('dialog');
    await form.getByLabel('Product specifications').fill('1500 W handheld garment steamer, 260 ml tank, 220 V, 0.9 kg.');
    await form.getByLabel('Intended use').fill('Retail sale to consumers in Lagos');
    await form.getByLabel('Your question').fill('Which classification applies and what certification is required?');
    await form.getByLabel('Candidate HS code').fill('8451.30');
    await form.getByRole('button', { name: 'Send to a reviewer' }).click();
    await expect(form).toBeHidden();

    await expect(page.getByText('Waiting for a reviewer')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Decide this review' })).toHaveCount(0);
    await expect(page.getByText(/waiting for a different workspace reviewer/i)).toBeVisible();
    // The gate also cannot be cleared from the Decision Room dropdown.
    await page.goto(`/decisions?product=${new URL(page.url()).searchParams.get('product') ?? ''}`);
    await page.goto('/decisions');
    await expect(page.getByLabel('Import status')).toHaveValue('unresolved');
    const options = await page.getByLabel('Import status').locator('option').allTextContents();
    // 'unresolved' is fine; what must not appear is an option that clears the gate.
    expect(options.join(' ')).not.toMatch(/\bapproved\b|\bresolved\b/i);
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('a reviewer decision resolves the gate and the assessment records it', async ({ page, browser, workspace }) => {
    const name = 'Reviewed candidate';
    await captureAndConfirm(page, asin(53), name);
    await page.goto('/discover');
    await page.getByRole('link', { name: new RegExp(name) }).click();
    const productUrl = page.url();
    const productId = page.url().split('/').pop()!;
    await page.getByRole('button', { name: 'Local viability' }).click();

    await page.getByRole('button', { name: 'Request a review' }).click();
    const request = page.getByRole('dialog');
    await request.getByLabel('Product specifications').fill('1500 W handheld garment steamer, 260 ml tank, 220 V.');
    await request.getByLabel('Intended use').fill('Retail sale to consumers in Lagos');
    await request.getByLabel('Your question').fill('Which classification applies before import?');
    await request.getByRole('button', { name: 'Send to a reviewer' }).click();
    await expect(request).toBeHidden();

    const reviewer = await inviteReviewer(page, browser);
    await reviewer.page.goto(productUrl);
    await reviewer.page.getByRole('button', { name: 'Local viability' }).click();
    await reviewer.page.getByRole('button', { name: 'Decide this review' }).click();
    const decision = reviewer.page.getByRole('dialog');
    await expect(decision.getByText('Retail sale to consumers in Lagos')).toBeVisible();
    await decision.getByLabel('Rationale').fill('Classified as a domestic steam appliance under the cited guideline.');
    await decision.getByLabel('Confirmed HS code').fill('8451.30.00');
    await decision.getByLabel('Requirements, one per line').fill('Product certificate before shipment');
    await decision.getByLabel('Source title').fill('Import guidelines, chapter 84');
    await decision.getByLabel('Source publisher').fill('Example regulator');
    await decision.getByLabel('Source link').fill('https://example-regulator.test/guidelines/84');
    await decision.getByLabel('Effective from').fill('2026-01-01');
    await decision.getByRole('button', { name: 'Record this decision' }).click();
    await expect(decision).toBeHidden();
    await reviewer.context.close();

    await page.reload();
    await page.getByRole('button', { name: 'Local viability' }).click();
    await expect(page.getByText('Approved', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('8451.30.00')).toBeVisible();
    await expect(page.getByText('Product certificate before shipment')).toBeVisible();

    // The saved assessment records which review resolved its gate.
    await page.goto(`/decisions?product=${productId}`);
    await fillDecisionInputs(page);
    await page.getByRole('button', { name: 'Save this decision' }).click();
    await expect(page.getByText(/That assessment is immutable/)).toBeVisible();
    expect(productUrl).toContain('/products/');
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('the demo GO example passes the same gates on clearly synthetic evidence', async ({ page }) => {
    await enterDemo(page);
    await page.goto('/decisions');
    await page.getByLabel('Choose product').selectOption({ label: 'Portable garment steamer' });

    await expect(page.getByText('GO', { exact: true }).first()).toBeVisible();
    // It is a demo, and every screen says so.
    await expect(page.getByText('DEMO WORKSPACE', { exact: true })).toBeVisible();
    await expect(page.getByText(/illustrative demo assumptions/)).toBeVisible();

    await page.goto('/discover');
    await page.getByRole('link', { name: /Portable garment steamer/ }).click();
    await page.getByRole('button', { name: 'Local viability' }).click();
    await expect(page.getByText(/synthetic fixture, not a regulatory opinion/)).toBeVisible();
    await expect(page.getByText('Independent demand metrics')).toBeVisible();
  });
});

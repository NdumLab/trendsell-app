import { asin, captureAndConfirm, expect, fillDecisionInputs, test } from './fixtures';

/** Capture → confirm → decision → watch, plus quote entry (action plan T02). */
test.describe('a complete manual investigation', () => {
  test('captures a product, confirms it, saves a decision and watches it', async ({ page, workspace }) => {
    const name = 'Portable garment steamer';
    await captureAndConfirm(page, asin(11), name);

    await page.goto('/discover');
    await expect(page.getByRole('link', { name: new RegExp(name) })).toBeVisible();

    await page.goto('/decisions');
    await expect(page.getByLabel('Choose product')).toHaveValue(/.+/);
    await fillDecisionInputs(page);
    // No collector is connected, so the honest verdict is that evidence is missing.
    await expect(page.getByText('Needs evidence').first()).toBeVisible();
    await page.getByRole('button', { name: 'Save this decision' }).click();
    await expect(page.getByText(/That assessment is immutable/)).toBeVisible();

    await page.getByRole('button', { name: /Saved decisions/ }).click();
    const history = page.getByRole('dialog');
    await expect(history.getByRole('heading', { name })).toBeVisible();
    await expect(history.getByText('unit-economics/1.1.0')).toBeVisible();
    await page.getByRole('button', { name: 'Close dialog' }).click();

    await page.goto('/discover');
    await page.getByRole('link', { name: new RegExp(name) }).click();
    await page.getByRole('button', { name: 'Watch product' }).click();
    await page.goto('/watchtower');
    await expect(page.getByRole('heading', { name: new RegExp(name) })).toBeVisible();
    await expect(page.getByText('Monitoring unavailable')).toBeVisible();
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('records a supplier quote and keeps its cents on screen', async ({ page, workspace }) => {
    const name = 'Quoted product';
    await captureAndConfirm(page, asin(12), name);

    await page.goto('/suppliers');
    await page.getByRole('button', { name: 'Add a quote' }).click();
    const form = page.getByRole('dialog');
    // The picker searches the server, so it is located by role: its wrapping <label>
    // contains the option text, and "Product" as a label substring also matches the
    // picker's own search box.
    await form.getByRole('combobox', { name: 'Product' }).selectOption({ label: name });
    await form.getByLabel('Supplier name').fill('Example Manufacturing Ltd');
    await form.getByLabel('Supplier or quote source URL').fill('https://supplier.example.com/quote-4821');
    await form.getByLabel('Unit price', { exact: true }).fill('8.40');
    await form.getByLabel('Minimum order (units)').fill('300');
    await form.getByLabel('Lead time (days)').fill('25');
    await form.getByLabel('Quote date').fill('2026-09-01');
    await form.getByRole('button', { name: 'Save quote' }).click();
    await expect(form).toBeHidden();

    // Review finding 6: this used to render as US$8.
    await expect(page.getByRole('cell', { name: /8\.40/ })).toBeVisible();
    await expect(page.getByText('Unverified').first()).toBeVisible();
  });

  test('an unusable supplier reference is refused rather than stored', async ({ page, workspace }) => {
    const name = 'Validated product';
    await captureAndConfirm(page, asin(13), name);
    await page.goto('/suppliers');
    await page.getByRole('button', { name: 'Add a quote' }).click();
    const form = page.getByRole('dialog');
    // The picker searches the server, so it is located by role: its wrapping <label>
    // contains the option text, and "Product" as a label substring also matches the
    // picker's own search box.
    await form.getByRole('combobox', { name: 'Product' }).selectOption({ label: name });
    await form.getByLabel('Supplier name').fill('Example Manufacturing Ltd');
    // The browser's own url validation would block "https://", so use a shape it accepts.
    await form.getByLabel('Supplier or quote source URL').fill('https://localhost');
    await form.getByLabel('Unit price', { exact: true }).fill('8.40');
    await form.getByLabel('Minimum order (units)').fill('300');
    await form.getByLabel('Lead time (days)').fill('25');
    await form.getByLabel('Quote date').fill('2026-09-01');
    await form.getByRole('button', { name: 'Save quote' }).click();
    await expect(form).toBeVisible();
    await expect(page.getByText(/https:\/\/ address/).first()).toBeVisible();
  });

  test('a decision cannot be saved before the product identity is confirmed', async ({ page, workspace }) => {
    await page.goto('/xray');
    await page.getByLabel('What are you investigating?').fill(asin(14));
    await page.getByRole('button', { name: 'Start investigation' }).click();
    await expect(page.getByRole('heading', { name: 'Confirm the product' })).toBeVisible();

    await page.goto('/decisions');
    await fillDecisionInputs(page);
    await expect(page.getByRole('button', { name: 'Save this decision' })).toBeDisabled();
    await expect(page.getByText('Confirm product identity in X-Ray before saving.')).toBeVisible();
  });
});

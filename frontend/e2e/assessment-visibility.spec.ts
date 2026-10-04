import { asin, captureAndConfirm, expect, fillDecisionInputs, test } from './fixtures';

/** A saved assessment is visible wherever the product is, without overwriting its
 *  evidence status (action plan T07, review finding 7). */
test.describe('saved assessments beside evidence status', () => {
  test('a prohibited assessment shows on the product, in Discover and on the watchlist', async ({ page, workspace }) => {
    const name = 'Prohibited candidate';
    await captureAndConfirm(page, asin(31), name);

    await page.goto('/decisions');
    await fillDecisionInputs(page);
    await page.getByLabel('Import status').selectOption('prohibited');
    await page.getByRole('button', { name: 'Save this decision' }).click();
    await expect(page.getByText(/That assessment is immutable/)).toBeVisible();

    await page.goto('/discover');
    // Chrome exposes an unnamed <article> as a generic node, so locate the card by class.
    const card = page.locator('.product-card').filter({ hasText: name });
    // Both facts on the same card: evidence is still missing, and the user said NO-GO.
    await expect(card.locator('.evidence-status .decision')).toHaveText('Needs evidence');
    await expect(card.getByText('Your latest assessment')).toBeVisible();
    await expect(card.locator('.assessment-summary .decision')).toHaveText('NO-GO');

    await page.getByRole('link', { name: new RegExp(name) }).click();
    await expect(page.getByText('Evidence status')).toBeVisible();
    await expect(page.getByText('Your latest assessment').first()).toBeVisible();
    await expect(page.getByText(/Marked prohibited by the person who saved it/)).toBeVisible();

    await page.getByRole('button', { name: 'Watch product' }).click();
    await page.goto('/watchtower');
    const row = page.locator('.watch-row').filter({ hasText: name });
    await expect(row.locator('.watch-verdicts .decision').first()).toHaveText('Needs evidence');
    await expect(row.locator('.assessment-summary .decision')).toHaveText('NO-GO');
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('a loss-making scenario reports failing economics and missing evidence together', async ({ page, workspace }) => {
    const name = 'Loss-making candidate';
    await captureAndConfirm(page, asin(32), name);
    await page.goto('/decisions');
    await fillDecisionInputs(page, { 'Target selling price': '9000' });
    await page.getByRole('button', { name: 'Save this decision' }).click();
    await expect(page.getByText(/That assessment is immutable/)).toBeVisible();

    await page.goto(`/discover`);
    await page.getByRole('link', { name: new RegExp(name) }).click();
    // Evidence is unverified *and* the economics do not work: neither hides the other.
    await expect(page.getByText('Evidence status')).toBeVisible();
    await expect(page.getByText('Needs evidence').first()).toBeVisible();
    await expect(page.getByText(/Economics fail/)).toBeVisible();
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('a product with no saved assessment says so instead of implying one', async ({ page, workspace }) => {
    const name = 'Unassessed candidate';
    await captureAndConfirm(page, asin(33), name);
    await page.goto('/discover');
    await page.getByRole('link', { name: new RegExp(name) }).click();
    await expect(page.getByText('No saved assessment').first()).toBeVisible();
    expect(workspace.workspace).toBe('E2E workspace');
  });
});

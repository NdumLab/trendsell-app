import { expect, fillDecisionInputs, test } from './fixtures';

/**
 * Fixture-backed browser acceptance only. The API factory returns deterministic local
 * provider fixtures and performs no external collection; this test is never live-data
 * proof. It proves that collected-shape records actually reach user-visible screens.
 */
test.describe('fixture-backed keyword-to-economics integration', () => {
  test('shows candidates, resolved evidence, local limitations, typed health, and an honest decision', async ({ page, workspace }) => {
    await page.goto('/xray');
    await page.getByRole('button', { name: 'Keyword' }).click();
    await page.getByLabel('Find current product candidates').fill('fixture portable steamer');
    await page.getByRole('button', { name: 'Find candidates' }).click();

    const candidates = page.locator('.discovery-panel');
    await expect(candidates.getByText('[Fixture] Portable garment steamer')).toBeVisible();
    await expect(candidates.getByText(/Candidate only · exact match incomplete/)).toBeVisible();
    await expect(candidates.getByText(/not recommendations, verified sales or attribution/)).toBeVisible();
    await candidates.getByRole('button', { name: 'Investigate' }).click();

    await expect(page.getByRole('heading', { name: 'Product identity resolved' })).toBeVisible();
    await expect(page.locator('.confirmation').getByText(/Selected from keyword/)).toContainText('must still resolve the exact ASIN');
    await page.getByRole('link', { name: 'View product evidence' }).click();

    await expect(page.getByRole('heading', { name: '[Fixture] Portable garment steamer' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Product identity provenance' })).toBeVisible();
    await expect(page.getByText('DataForSEO Amazon API', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Search-interest timeline' })).toBeVisible();
    await expect(page.locator('.timeline-panel').getByText(/Relative demand indicator · DataForSEO Trends · NG/)).toBeVisible();

    await page.locator('.observation-card').filter({ hasText: 'Search interest' }).click();
    const drawer = page.getByRole('dialog', { name: 'Follow the evidence' });
    await expect(drawer.getByText('DataForSEO Trends')).toBeVisible();
    await expect(drawer.getByText('dataforseo-live/1')).toBeVisible();
    await expect(drawer.getByText(/TEST FIXTURE ONLY/)).toBeVisible();
    await drawer.getByRole('button', { name: 'Close dialog' }).click();

    await page.getByRole('button', { name: 'Local viability' }).click();
    await expect(page.getByRole('heading', { name: 'Jumia Nigeria listing candidates' })).toBeVisible();
    await expect(page.getByText('[Fixture] Portable garment steamer 1200W')).toBeVisible();
    await expect(page.getByText(/not product equivalence or total-market coverage/)).toBeVisible();

    await page.getByRole('link', { name: 'Add your commercial assumptions' }).click();
    await fillDecisionInputs(page);
    const verdict = page.locator('.decision-verdict');
    await expect(verdict).toBeVisible();
    await expect(verdict.locator('.decision')).toHaveText(/WATCH|Needs evidence/);
    await expect(verdict).toContainText(/import readiness unresolved/);
    await expect(page.getByText('All amounts below come from you.')).toBeVisible();

    await page.goto('/data-health');
    const catalog = page.locator('[data-source-id="catalog"]');
    await expect(catalog).toContainText('Configurationconfigured');
    await expect(catalog).toContainText('Latest collectionsucceeded');
    await expect(catalog).toContainText('Stored observationsstored current');
    await expect(catalog).toContainText('API availabilityavailable');
    const local = page.locator('[data-source-id="local_market"]');
    await expect(local).toContainText('Stored observationsstored current');
    await expect(local).toContainText('API availabilityavailable');
    await expect(page.getByText(/API availability does not prove that a screen displays the evidence/)).toBeVisible();
    expect(workspace.workspace).toBe('E2E workspace');
  });
});

import { downloadJson, expect, test } from './fixtures';

/** Demo records stay separate from a real workspace, in storage and in downloads (T02/T03). */
test.describe('demo workspace', () => {
  test('entering and leaving the demo never mixes it with a signed-in workspace', async ({ page, workspace }) => {
    await page.goto('/');
    await expect(page.getByText('PILOT WORKSPACE')).toBeVisible();

    await page.getByRole('button', { name: /Explore demo/ }).click();
    await expect(page.getByText('DEMO WORKSPACE', { exact: true })).toBeVisible();
    await expect(page.getByText(/Synthetic examples/)).toBeVisible();

    await page.goto('/discover');
    await expect(page.getByRole('link', { name: /Portable garment steamer/ })).toBeVisible();

    await page.getByRole('button', { name: /Exit demo/ }).click();
    await expect(page.getByText('PILOT WORKSPACE')).toBeVisible();
    await page.goto('/discover');
    // The signed-in workspace is empty; no demo product may survive the switch.
    await expect(page.getByRole('link', { name: /Portable garment steamer/ })).toHaveCount(0);
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('a demo assessment is labelled demo in the app and in its download', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Explore demo/ }).click();
    await page.goto('/decisions');
    await expect(page.getByLabel('Choose product')).toBeVisible();
    await page.getByRole('button', { name: 'Save this decision' }).click();
    await expect(page.getByText(/That assessment is immutable/)).toBeVisible();

    const exported = await downloadJson(page, () =>
      page.getByRole('button', { name: 'Export saved assessment' }).click());
    expect(exported.body.demo).toBe(true);
    expect(exported.body.assessment.truth_state).toBe('Demo');
    expect(exported.body.evidence_version).toBe('demo-fixture/1');
    // Demo evidence travels with the demo assessment and is marked as an example.
    for (const observation of exported.body.evidence)
      expect(observation.truth_state).toBe('Demo');
  });

  test('a demo product is not reachable from a real workspace', async ({ page, workspace }) => {
    await page.goto('/products/demo-steamer');
    await expect(page.getByRole('heading', { name: 'Investigation not found' })).toBeVisible();
    expect(workspace.workspace).toBe('E2E workspace');
  });
});

import { asin, captureAndConfirm, downloadJson, expect, fillDecisionInputs, test } from './fixtures';

/** The two export defects the review reproduced in a browser (action plan T03). */
test.describe('export integrity', () => {
  test('changing an input after saving cannot export the previous assessment as current', async ({ page, workspace }) => {
    // Review finding 1: after saving, switching import status to "prohibited" changed the
    // verdict on screen to NO-GO while the export still produced the earlier WATCH result.
    await captureAndConfirm(page, asin(21), 'Export state product');
    await page.goto('/decisions');
    await fillDecisionInputs(page);
    await page.getByRole('button', { name: 'Save this decision' }).click();
    await expect(page.getByText(/That assessment is immutable/)).toBeVisible();

    const savedExport = await downloadJson(page, () =>
      page.getByRole('button', { name: 'Export saved assessment' }).click());
    expect(savedExport.body.source).toBe('saved assessment');
    const savedDecision = savedExport.body.assessment.decision;

    await page.getByLabel('Import status').selectOption('prohibited');
    await expect(page.getByText('NO-GO')).toBeVisible();

    // The saved reference is gone, so there is no stale "saved" export to download at all.
    await expect(page.getByRole('button', { name: 'Export saved assessment' })).toHaveCount(0);
    await expect(page.getByText(/Nothing on screen is saved yet/)).toBeVisible();

    const draft = await downloadJson(page, () => page.getByRole('button', { name: 'Export this draft' }).click());
    expect(draft.body.source).toBe('unsaved draft');
    expect(draft.body.saved).toBe(false);
    expect(draft.body.assessment.decision).toBe('NO-GO');
    expect(draft.body.assessment.inputs.compliance).toBe('prohibited');
    expect(savedDecision).not.toBe('NO-GO');
    expect(workspace.workspace).toBe('E2E workspace');
  });

  for (const [label, identifier] of [['Sales channel', 22], ['Freight mode', 23]] as const)
  test(`changing ${label} also invalidates the saved reference`, async ({ page, workspace }) => {
    await captureAndConfirm(page, asin(identifier), `Invalidated by ${label}`);
    await page.goto('/decisions');
    await fillDecisionInputs(page);
    await page.getByRole('button', { name: 'Save this decision' }).click();
    await expect(page.getByRole('button', { name: 'Export saved assessment' })).toBeVisible();

    await page.getByLabel(label).selectOption({ index: 1 });
    await expect(page.getByRole('button', { name: 'Export saved assessment' })).toHaveCount(0);
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('a historical assessment downloads its own evidence, not the open product’s', async ({ page, workspace }) => {
    // Review finding 2: saving product A, selecting product B, then downloading A from
    // history produced A's assessment carrying B's observations.
    const first = 'Steamer under review';
    const second = 'Blender under review';
    await captureAndConfirm(page, asin(24), first);
    await captureAndConfirm(page, asin(25), second);

    await page.goto('/decisions');
    await page.getByLabel('Choose product').selectOption({ label: first });
    await fillDecisionInputs(page);
    await page.getByRole('button', { name: 'Save this decision' }).click();
    await expect(page.getByText(/That assessment is immutable/)).toBeVisible();

    // Move the editor to the other product, exactly as the reproduction did.
    await page.getByLabel('Choose product').selectOption({ label: second });
    await fillDecisionInputs(page, { 'Target selling price': '20000' });

    await page.getByRole('button', { name: /Saved decisions/ }).click();
    const history = page.getByRole('dialog');
    await expect(history.getByRole('heading', { name: first })).toBeVisible();
    const downloaded = await downloadJson(page, () =>
      history.getByRole('button', { name: 'Download assessment' }).first().click());

    expect(downloaded.body.product.name).toBe(first);
    expect(downloaded.body.assessment.product_name).toBe(first);
    // The open editor is showing the other product; none of it may appear here.
    expect(JSON.stringify(downloaded.body)).not.toContain(second);
    // Provenance is the assessment's own, never a current constant.
    expect(downloaded.body.evidence).toEqual([]);
    expect(downloaded.body.assessment.observation_ids).toEqual([]);
    expect(downloaded.body.threshold_version).toBe(downloaded.body.assessment.threshold_version);
    expect(downloaded.body.formula_version).toBe(downloaded.body.assessment.formula_version);
    expect(downloaded.body.evidence_version).toBe('evidence-quality/1.0.0');
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('a saved export stays identical while the editor keeps changing', async ({ page, workspace }) => {
    await captureAndConfirm(page, asin(26), 'Immutable product');
    await page.goto('/decisions');
    await fillDecisionInputs(page);
    await page.getByRole('button', { name: 'Save this decision' }).click();
    const before = await downloadJson(page, () =>
      page.getByRole('button', { name: 'Export saved assessment' }).click());

    await fillDecisionInputs(page, { 'Target selling price': '99000', 'Order quantity': '17' });
    await page.getByRole('button', { name: /Saved decisions/ }).click();
    const history = page.getByRole('dialog');
    const after = await downloadJson(page, () =>
      history.getByRole('button', { name: 'Download assessment' }).first().click());

    expect(after.body.assessment).toEqual(before.body.assessment);
    expect(after.body.evidence).toEqual(before.body.evidence);
    expect(workspace.workspace).toBe('E2E workspace');
  });
});

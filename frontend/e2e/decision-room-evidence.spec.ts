import { apiProduct, asin, downloadJson, expect, fillDecisionInputs, recordFullCoverage, test } from './fixtures';

/** Decision Room reads the server's evidence, not a stale list payload (review finding R01).
 *
 *  The regression: `/api/v1/products` returns stored product payloads with no computed
 *  `evidence_quality`, and this screen preferred that list object — fetching the detail
 *  only when the product was absent from the loaded pages. An ordinary product is always
 *  on the first page, so it never got the reading. The draft on screen said INSUFFICIENT
 *  EVIDENCE at confidence 0 while saving the very same inputs produced WATCH at 60, and
 *  the draft export claimed `no-observations/1` with zero evidence records attached.
 */
test.describe('decision room reads recorded evidence', () => {
  test('an unchanged draft and the saved assessment agree exactly', async ({ page, workspace }) => {
    const productId = await apiProduct(page, asin(61), 'Evidence agreement candidate');
    await recordFullCoverage(page, productId);

    await page.goto(`/decisions?product=${productId}`);
    await expect(page.getByLabel('Choose product')).toHaveValue(productId);
    await fillDecisionInputs(page);

    const draft = await downloadJson(page, () =>
      page.getByRole('button', { name: 'Export this draft' }).click());
    await page.getByRole('button', { name: 'Save this decision' }).click();
    await expect(page.getByText(/That assessment is immutable/)).toBeVisible();
    const saved = await downloadJson(page, () =>
      page.getByRole('button', { name: 'Export saved assessment' }).click());

    // Same inputs, same evidence, so the two must not disagree on anything that matters.
    expect(draft.body.assessment.confidence).toBe(saved.body.assessment.confidence);
    expect(draft.body.assessment.decision).toBe(saved.body.assessment.decision);
    expect(draft.body.assessment.blockers).toEqual(saved.body.assessment.blockers);
    expect(draft.body.evidence.length).toBe(4);
    expect(draft.body.evidence.length).toBe(saved.body.evidence.length);
    expect(draft.body.evidence_version).toBe(saved.body.evidence_version);
    expect(draft.body.evidence_version).not.toBe('no-observations/1');
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('the reading matches what the product detail independently reports', async ({ page, workspace }) => {
    const productId = await apiProduct(page, asin(62), 'Server agreement candidate');
    await recordFullCoverage(page, productId);
    const detail = await (await page.request.get(`/api/v1/products/${productId}`)).json();

    await page.goto(`/decisions?product=${productId}`);
    await fillDecisionInputs(page);
    // The manual-only cap is 60, so this is the score the method actually produces.
    expect(detail.confidence).toBe(60);
    await expect(page.getByText(`${detail.confidence}`).first()).toBeVisible();
    const draft = await downloadJson(page, () =>
      page.getByRole('button', { name: 'Export this draft' }).click());
    expect(draft.body.assessment.confidence).toBe(detail.confidence);
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('a product on the first page gets its evidence, not only a linked one', async ({ page, workspace }) => {
    // The exact shape of the regression: nothing here is past a page boundary.
    const productId = await apiProduct(page, asin(63), 'First page candidate');
    await recordFullCoverage(page, productId);

    await page.goto('/decisions');
    await page.getByLabel('Choose product').selectOption(productId);
    await fillDecisionInputs(page);
    const draft = await downloadJson(page, () =>
      page.getByRole('button', { name: 'Export this draft' }).click());
    expect(draft.body.assessment.confidence).toBe(60);
    expect(draft.body.assessment.decision).not.toBe('INSUFFICIENT EVIDENCE');
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('a reviewer rejection decides the draft without the user restating it', async ({ page, workspace }) => {
    const productId = await apiProduct(page, asin(64), 'Rejected candidate');
    await recordFullCoverage(page, productId);
    const headers = { 'X-Requested-With': 'TrendSell' };
    const requested = await page.request.post(`/api/v1/products/${productId}/compliance/requests`, {
      headers,
      data: { product_id: productId, destination: 'NG',
              specifications: '1500 W handheld garment steamer, 260 ml tank, 220 V, 0.9 kg.',
              intended_use: 'Retail sale to consumers in Lagos',
              question: 'Which classification applies and is import permitted?' },
    });
    expect(requested.status(), await requested.text()).toBe(201);
    const decided = await page.request.post(
      `/api/v1/compliance/reviews/${(await requested.json()).id}/decision`,
      { headers, data: { status: 'rejected', rationale: 'Not permitted for import as specified.' } });
    expect(decided.status(), await decided.text()).toBe(200);

    await page.goto(`/decisions?product=${productId}`);
    await fillDecisionInputs(page);
    // The dropdown is left at its default: the reviewer is not repeated by hand.
    await expect(page.getByLabel('Import status')).toHaveValue('unresolved');
    const draft = await downloadJson(page, () =>
      page.getByRole('button', { name: 'Export this draft' }).click());
    expect(draft.body.assessment.decision).toBe('NO-GO');
    expect(draft.body.assessment.blockers[0]).toBe(
      'A reviewer rejected this product for import. Do not proceed.');

    await page.getByRole('button', { name: 'Save this decision' }).click();
    await expect(page.getByText(/That assessment is immutable/)).toBeVisible();
    const saved = await downloadJson(page, () =>
      page.getByRole('button', { name: 'Export saved assessment' }).click());
    expect(saved.body.assessment.decision).toBe('NO-GO');
    expect(saved.body.assessment.inputs.compliance).toBe('unresolved');
    expect(workspace.workspace).toBe('E2E workspace');
  });

  test('an approved review resolves the gate the draft reports', async ({ page, workspace }) => {
    const productId = await apiProduct(page, asin(65), 'Approved candidate');
    await recordFullCoverage(page, productId);
    const headers = { 'X-Requested-With': 'TrendSell' };
    const requested = await page.request.post(`/api/v1/products/${productId}/compliance/requests`, {
      headers,
      data: { product_id: productId, destination: 'NG',
              specifications: '1500 W handheld garment steamer, 260 ml tank, 220 V, 0.9 kg.',
              intended_use: 'Retail sale to consumers in Lagos',
              question: 'Which classification applies before import?' },
    });
    const decided = await page.request.post(
      `/api/v1/compliance/reviews/${(await requested.json()).id}/decision`,
      { headers, data: { status: 'approved', hs_code: '8451.30.00',
                         rationale: 'Classified as a domestic steam appliance under the cited guideline.',
                         requirements: ['Product certificate before shipment'],
                         sources: [{ title: 'Import guidelines, chapter 84',
                                     url: 'https://example-regulator.test/guidelines/84',
                                     publisher: 'Example regulator', effective_from: '2026-01-01' }] } });
    expect(decided.status(), await decided.text()).toBe(200);

    await page.goto(`/decisions?product=${productId}`);
    await fillDecisionInputs(page);
    await expect(page.getByText(/import readiness approved/)).toBeVisible();
    const draft = await downloadJson(page, () =>
      page.getByRole('button', { name: 'Export this draft' }).click());
    expect(draft.body.assessment.decision).not.toBe('NO-GO');
    expect(draft.body.assessment.blockers).not.toContain(
      'Obtain a reviewed product classification and current import requirements.');
    expect(workspace.workspace).toBe('E2E workspace');
  });
});

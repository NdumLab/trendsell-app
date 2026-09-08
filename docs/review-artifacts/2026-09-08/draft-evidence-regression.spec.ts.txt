// Review artifact: copy into frontend/e2e/ to execute with the existing Playwright fixtures.
import { writeFileSync } from 'node:fs';
import { asin, downloadJson, expect, fillDecisionInputs, test } from './fixtures';

test('independent review: draft must use the evidence used by the saved decision', async ({page, workspace}) => {
  const headers = {'X-Requested-With':'TrendSell'};
  const job = await page.request.post('/api/v1/xray', {headers, data:{input:asin(901)}});
  expect(job.status()).toBe(202);
  const pid = (await job.json()).product_id;
  expect((await page.request.post(`/api/v1/products/${pid}/confirm`, {headers, data:{name:'Independent review candidate'}})).status()).toBe(200);
  for (const [index, metric] of ['Search interest','Review velocity','Social mentions','Local listing count'].entries()) {
    const response = await page.request.post(`/api/v1/products/${pid}/evidence`, {headers, data:{metric,value:100,unit:'count',market:index===3?'NG':'US',observed_at:new Date().toISOString().slice(0,10),source_name:`Review source ${index}`,method:'Disposable manually entered test fixture'}});
    expect(response.status()).toBe(201);
  }
  await page.goto(`/decisions?product=${pid}`);
  await expect(page.getByLabel('Choose product')).toHaveValue(pid);
  await fillDecisionInputs(page, {'Supplier unit quote':'2','Total freight quote':'90000'});
  const detail = await (await page.request.get(`/api/v1/products/${pid}`)).json();
  const draft = await downloadJson(page, () => page.getByRole('button',{name:'Export this draft'}).click());
  await page.getByRole('button',{name:'Save this decision'}).click();
  await expect(page.getByText(/That assessment is immutable/)).toBeVisible();
  const saved = await downloadJson(page, () => page.getByRole('button',{name:'Export saved assessment'}).click());
  const result = {detail_confidence:detail.confidence, draft_confidence:draft.body.assessment.confidence,
    saved_confidence:saved.body.assessment.confidence,draft_decision:draft.body.assessment.decision,
    saved_decision:saved.body.assessment.decision,draft_evidence_count:draft.body.evidence.length,
    saved_evidence_count:saved.body.evidence.length,draft_evidence_version:draft.body.evidence_version,
    verdict_text:await page.locator('.decision-verdict').innerText()};
  writeFileSync('/tmp/trendsell_review_browser_results.json',JSON.stringify(result,null,2));
  expect(workspace.workspace).toBe('E2E workspace');
  expect.soft(draft.body.assessment.confidence).toBe(saved.body.assessment.confidence);
  expect.soft(draft.body.evidence.length).toBe(4);
  expect.soft(draft.body.assessment.decision).toBe(saved.body.assessment.decision);
});

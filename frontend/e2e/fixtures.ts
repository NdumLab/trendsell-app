import { expect, test as base, type Page } from '@playwright/test';

/** Shared browser fixtures (action plan T02).
 *
 *  Every test signs into its own throwaway workspace on the disposable API that
 *  playwright.config.ts starts. Nothing here touches a real workspace or a real source.
 */

export const PASSWORD = 'an-e2e-password-1';
/** Valid ASIN shapes. No request leaves the machine: the API parses identifiers only. */
export const asin = (n: number) => `B0E2E${String(n).padStart(5, '0')}`;

let accounts = 0;
export const uniqueEmail = () => `e2e-${Date.now()}-${accounts++}@example.test`;

/** Sign in through the API using the page's own cookie jar.
 *
 *  This exercises the real session cookie and CSRF header without retyping the dialog in
 *  every test; `auth.spec.ts` drives the dialog itself.
 */
export async function signIn(page: Page, workspace = 'E2E workspace') {
  const email = uniqueEmail();
  const response = await page.request.post('/api/v1/auth/register', {
    headers: { 'X-Requested-With': 'TrendSell' },
    data: { email, password: PASSWORD, name: workspace },
  });
  expect(response.status(), await response.text()).toBe(201);
  return { email, workspace };
}

/** Capture a product and confirm its identity, which a saved decision requires. */
export async function captureAndConfirm(page: Page, identifier: string, name: string) {
  await page.goto('/xray');
  await page.getByLabel('What are you investigating?').fill(identifier);
  await page.getByRole('button', { name: 'Start investigation' }).click();
  await expect(page.getByRole('heading', { name: 'Confirm the product' })).toBeVisible();
  await page.getByLabel('Product name').fill(name);
  await page.getByRole('button', { name: 'Confirm this product' }).click();
  await expect(page.getByRole('link', { name: 'View product evidence' })).toBeVisible();
  return name;
}

/** The commercial inputs Decision Room needs before it will calculate anything. */
export const DECISION_INPUTS: Record<string, string> = {
  'Order quantity': '300',
  'Supplier unit quote': '8.4',
  'Your exchange rate': '1500',
  'Total freight quote': '900000',
  'Duty assumption': '5',
  'Import tax assumption': '7.5',
  'Target selling price': '32000',
  'Channel & payment fees': '5',
  'Returns allowance': '3',
  'Total marketing budget': '300000',
  'Fixed costs & reserves': '150000',
};

export async function fillDecisionInputs(page: Page, overrides: Record<string, string> = {}) {
  for (const [label, value] of Object.entries({ ...DECISION_INPUTS, ...overrides }))
    await page.getByLabel(label, { exact: true }).fill(value);
}

/** Capture the JSON of the next download the page starts. */
export async function downloadJson(page: Page, trigger: () => Promise<void>) {
  const [download] = await Promise.all([page.waitForEvent('download'), trigger()]);
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk));
  return { name: download.suggestedFilename(), body: JSON.parse(Buffer.concat(chunks).toString('utf8')) };
}

export const test = base.extend<{ workspace: { email: string; workspace: string } }>({
  workspace: async ({ page }, use) => {
    await use(await signIn(page));
  },
});

export { expect };

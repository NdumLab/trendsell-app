import { expect, test as base, type Browser, type BrowserContext, type Page } from '@playwright/test';

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

/** Enter the demo workspace and wait until it is actually active.
 *
 *  `enterDemo` loads its fixtures through a dynamic import and only marks the mode in
 *  sessionStorage once that resolves, so a navigation issued straight after the click can
 *  outrun it and land back in the pilot workspace. Waiting for the banner ties the next
 *  navigation to the state it depends on instead of to the module graph being warm.
 */
export async function enterDemo(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: /Explore demo/ }).click();
  await expect(page.getByText('DEMO WORKSPACE', { exact: true })).toBeVisible();
}

/** Record one manual observation through the API, as the evidence screen does. */
export async function recordEvidence(page: Page, productId: string, metric: string, market: 'US'|'NG', source: string) {
  const response = await page.request.post(`/api/v1/products/${productId}/evidence`, {
    headers: { 'X-Requested-With': 'TrendSell' },
    data: { metric, value: 68, unit: 'index / 100', market,
            observed_at: new Date(Date.now() - 3 * 86_400_000).toISOString().slice(0, 10),
            source_name: source, method: 'Disposable manually entered test fixture.' },
  });
  expect(response.status(), await response.text()).toBe(201);
}

/** Enough independent, current evidence for the method to score a product. */
export async function recordFullCoverage(page: Page, productId: string) {
  await recordEvidence(page, productId, 'Search interest', 'US', 'Search trends export');
  await recordEvidence(page, productId, 'Review velocity', 'US', 'Marketplace listing page');
  await recordEvidence(page, productId, 'Marketplace rank', 'US', 'Marketplace category page');
  await recordEvidence(page, productId, 'Local listing price', 'NG', 'Lagos market survey');
}

/** Capture and confirm a product through the API, returning its id. */
export async function apiProduct(page: Page, identifier: string, name: string) {
  const headers = { 'X-Requested-With': 'TrendSell' };
  const job = await page.request.post('/api/v1/xray', { headers, data: { input: identifier } });
  expect(job.status(), await job.text()).toBe(202);
  const productId = (await job.json()).product_id as string;
  const confirmed = await page.request.post(`/api/v1/products/${productId}/confirm`,
                                            { headers, data: { name } });
  expect(confirmed.status(), await confirmed.text()).toBe(200);
  return productId;
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

/** The local mail sink this run's API writes to (playwright.config.ts sets both).
 *
 *  Reading the token out of the message is the point: it exercises the delivery path a
 *  person actually uses, rather than reaching into the database and testing a token table.
 */
export function mailDir() {
  const directory = process.env.TRENDSELL_E2E_MAIL_DIR;
  if (!directory) throw new Error('TRENDSELL_E2E_MAIL_DIR is not set by playwright.config.ts');
  return directory;
}

/** The newest message of one purpose, waiting briefly for it to be written. */
type MailPurpose = 'password_reset' | 'email_verification' | 'workspace_invitation';

export async function latestMessage(purpose: MailPurpose) {
  const { readdirSync, readFileSync } = await import('node:fs');
  const { join } = await import('node:path');
  for (let attempt = 0; attempt < 40; attempt++) {
    let files: string[] = [];
    try { files = readdirSync(mailDir()).filter(name => name.endsWith(`-${purpose}.json`)).sort(); }
    catch { files = []; }
    if (files.length) {
      const body = JSON.parse(readFileSync(join(mailDir(), files[files.length - 1]), 'utf8'));
      return body as { to: string; subject: string; purpose: string; body: string };
    }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`no ${purpose} message was written to the sink`);
}

/** The token a message carries, as the person reading it would copy it out. */
export async function tokenFrom(purpose: MailPurpose) {
  const message = await latestMessage(purpose);
  const label = purpose === 'password_reset' ? 'Reset token:'
    : purpose === 'email_verification' ? 'Verification token:' : 'Invitation token:';
  const line = message.body.split('\n').find(text => text.startsWith(label));
  if (!line) throw new Error(`no ${label} line in the ${purpose} message`);
  return line.slice(label.length).trim();
}

/** Invite and sign in a real second reviewer through the shipped membership flow. */
export async function inviteReviewer(owner: Page, browser: Browser): Promise<{
  context: BrowserContext; page: Page; email: string;
}> {
  const email = uniqueEmail();
  const invited = await owner.request.post('/api/v1/workspace/invitations', {
    headers: { 'X-Requested-With': 'TrendSell' },
    data: { email, role: 'reviewer' },
  });
  expect(invited.status(), await invited.text()).toBe(201);
  const token = await tokenFrom('workspace_invitation');
  const probe = await owner.request.get('/api/v1/config');
  const context = await browser.newContext({ baseURL: new URL(probe.url()).origin });
  const reviewer = await context.newPage();
  const accepted = await reviewer.request.post('/api/v1/auth/invitations/accept', {
    headers: { 'X-Requested-With': 'TrendSell' },
    data: { token, name: 'Independent reviewer', password: PASSWORD },
  });
  expect(accepted.status(), await accepted.text()).toBe(201);
  return { context, page: reviewer, email };
}

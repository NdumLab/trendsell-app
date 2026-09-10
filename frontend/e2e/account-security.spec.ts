import { PASSWORD, expect, test, tokenFrom, uniqueEmail } from './fixtures';

/** The browser half of account recovery and account security (action plan P03).
 *
 *  Every one of these flows existed only as an HTTP endpoint before this: a pilot user
 *  could not reset a password, change one, see their sessions, prove they owned their
 *  address, or delete their workspace without a client that speaks the API by hand.
 *
 *  The two token flows read the token out of the message the sink actually wrote, so
 *  what is exercised is the delivery path a person uses — not a token table.
 */

const NEW_PASSWORD = 'a-replacement-e2e-password';

/** Open the auth dialog the way a signed-out person does, from the workspace button. */
async function openAuthDialog(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page.getByRole('button', { name: /My workspace/ }).click();
  return page.getByRole('dialog');
}

async function signInThrough(page: import('@playwright/test').Page, email: string, password: string) {
  const dialog = await openAuthDialog(page);
  await dialog.getByLabel('Email address').fill(email);
  await dialog.getByLabel('Password').fill(password);
  await dialog.getByRole('button', { name: 'Sign in' }).click();
  return dialog;
}

test('a signed-in person can change their password, and the old one stops working', async ({ page, workspace }) => {
  await page.goto('/settings');
  await page.getByLabel('Current password').fill(PASSWORD);
  await page.getByLabel('New password', { exact: true }).fill(NEW_PASSWORD);
  await page.getByLabel('Confirm new password').fill(NEW_PASSWORD);
  await page.getByRole('button', { name: 'Change password' }).click();
  await expect(page.getByText(/Password changed/)).toBeVisible();

  // The change ended this session too, so the old password must not sign back in.
  await page.context().clearCookies();
  const refused = await signInThrough(page, workspace.email, PASSWORD);
  await expect(refused.getByRole('alert')).toBeVisible();
  const accepted = await signInThrough(page, workspace.email, NEW_PASSWORD);
  await expect(accepted).toBeHidden();
});

test('a locked-out person can reset their password from the sign-in dialog', async ({ page }) => {
  const email = uniqueEmail();
  await page.request.post('/api/v1/auth/register', {
    headers: { 'X-Requested-With': 'TrendSell' },
    data: { email, password: PASSWORD, name: 'Recovery workspace' },
  });
  await page.context().clearCookies();

  const dialog = await openAuthDialog(page);
  await dialog.getByRole('button', { name: 'Forgot your password?' }).click();
  await dialog.getByLabel('Email address').fill(email);
  await dialog.getByRole('button', { name: 'Send a reset link' }).click();

  const token = await tokenFrom('password_reset');
  await dialog.getByLabel('Reset token').fill(token);
  await dialog.getByLabel('New password').fill(NEW_PASSWORD);
  await dialog.getByRole('button', { name: 'Set a new password' }).click();
  await expect(page.getByText(/Password reset/)).toBeVisible();

  const accepted = await signInThrough(page, email, NEW_PASSWORD);
  await expect(accepted).toBeHidden();
});

test('the reset request says the same thing for an address with no workspace', async ({ page }) => {
  await page.context().clearCookies();
  const dialog = await openAuthDialog(page);
  await dialog.getByRole('button', { name: 'Forgot your password?' }).click();
  await dialog.getByLabel('Email address').fill('nobody-at-all@example.test');
  await dialog.getByRole('button', { name: 'Send a reset link' }).click();
  // It must not reveal that the account does not exist: the same next step either way.
  await expect(page.getByText(/If that address has a workspace/)).toBeVisible();
  await expect(dialog.getByLabel('Reset token')).toBeVisible();
});

test('a deployment without mail does not claim that it sent a reset message', async ({ page }) => {
  await page.route('**/api/v1/config', async route => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ response, json: { ...body, mail_delivery_configured: false } });
  });
  await page.route('**/api/v1/auth/recovery/request', route => route.fulfill({
    status: 202,
    contentType: 'application/json',
    body: JSON.stringify({
      detail: 'If the account exists, recovery instructions are available.',
      delivery_configured: false,
    }),
  }));

  await page.context().clearCookies();
  const dialog = await openAuthDialog(page);
  await dialog.getByRole('button', { name: 'Forgot your password?' }).click();
  await expect(dialog.getByText(/no mail transport configured/i)).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Continue to token' })).toBeVisible();
  await dialog.getByLabel('Email address').fill('owner@example.test');
  await dialog.getByRole('button', { name: 'Continue to token' }).click();

  await expect(page.getByText(/No message was sent/)).toBeVisible();
  await expect(dialog.getByLabel('Reset token')).toBeVisible();
});

test('a person can prove they own their address', async ({ page, workspace }) => {
  await page.goto('/settings');
  await expect(page.getByText('Not verified')).toBeVisible();

  const token = await tokenFrom('email_verification');
  await page.getByLabel('Verification token').fill(token);
  await page.getByRole('button', { name: 'Verify this address' }).click();
  await expect(page.getByText(/Email address verified/)).toBeVisible();
  await page.reload();
  await expect(page.getByText(/^Verified /)).toBeVisible();
  expect(workspace.workspace).toBe('E2E workspace');
});

test('a person can see their sessions and end another one', async ({ page, browser, workspace }) => {
  // A second sign-in on the same account, from a separate browser context.
  const other = await browser.newContext();
  const otherPage = await other.newPage();
  await otherPage.request.post('/api/v1/auth/login', {
    headers: { 'X-Requested-With': 'TrendSell' },
    data: { email: workspace.email, password: PASSWORD },
  });

  await page.goto('/settings');
  const sessions = page.locator('.settings-card', { hasText: 'Active sessions' });
  await expect(sessions.locator('tbody tr')).toHaveCount(2);
  await expect(sessions.getByText('This device')).toBeVisible();

  // End the one that is not this device.
  await sessions.locator('tbody tr', { hasNot: page.getByText('This device') })
    .getByRole('button', { name: 'End this session' }).click();
  await expect(page.getByText(/session was ended/)).toBeVisible();
  await expect(sessions.locator('tbody tr')).toHaveCount(1);

  // The ended session really is gone, not just delisted.
  const check = await otherPage.request.get('/api/v1/auth/me');
  expect(check.status()).toBe(401);
  await other.close();
});

test('deleting a workspace requires the password and the typed phrase, then removes it', async ({ page, workspace }) => {
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Delete workspace…' }).click();

  // The wrong phrase is refused.
  await page.getByLabel('Your password').fill(PASSWORD);
  await page.getByLabel(/Type .* to confirm/).fill('DELETE something else');
  await page.getByRole('button', { name: 'Permanently delete this workspace' }).click();
  await expect(page.getByRole('alert')).toBeVisible();

  await page.getByLabel(/Type .* to confirm/).fill(`DELETE ${workspace.workspace}`);
  await page.getByRole('button', { name: 'Permanently delete this workspace' }).click();
  await expect(page.getByText(/Workspace deleted/)).toBeVisible();

  // The account is gone: its former credentials no longer sign in.
  const check = await page.request.post('/api/v1/auth/login', {
    headers: { 'X-Requested-With': 'TrendSell' },
    data: { email: workspace.email, password: PASSWORD },
  });
  expect(check.status()).toBe(401);
});

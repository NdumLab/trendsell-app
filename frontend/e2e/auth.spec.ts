import { asin, captureAndConfirm, expect, latestMessage, test, tokenFrom, PASSWORD, uniqueEmail } from './fixtures';

/** Registration, sign-in, sign-out and an expired session (action plan T02). */
test.describe('account access', () => {
  test('the controlled tier is visibly free and invitation-only', async ({ page }) => {
    await page.route('**/api/v1/config', async route => {
      const response = await route.fetch();
      const body = await response.json();
      await route.fulfill({ response, json: {
        ...body, release_tier: 'controlled_pilot', invitation_only: true,
        billing_enabled: false, allow_registration: false,
      } });
    });
    await page.goto('/');
    await expect(page.getByText('FREE · INVITATION-ONLY PILOT')).toBeVisible();

    await page.getByRole('button', { name: /My workspace/ }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText(/free, invitation-only controlled pilot/i)).toBeVisible();
    await expect(dialog.getByRole('button', { name: /Create a workspace/ })).toHaveCount(0);
  });

  test('a visitor can create a workspace, sign out and sign back in', async ({ page }) => {
    const email = uniqueEmail();
    await page.goto('/');

    // The sidebar's workspace switch opens the auth dialog while signed out.
    await page.getByRole('button', { name: /My workspace/ }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: /New here\? Create a workspace/ }).click();
    await dialog.getByLabel('Workspace name').fill('Browser workspace');
    await dialog.getByLabel('Email address').fill(email);
    await dialog.getByLabel('Password').fill(PASSWORD);
    await dialog.getByRole('button', { name: 'Create workspace' }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByText('Browser workspace').first()).toBeVisible();

    await page.goto('/settings');
    await page.getByRole('button', { name: /Sign out/ }).click();
    await expect(page.getByRole('button', { name: /My workspace/ })).toBeVisible();

    await page.getByRole('button', { name: /My workspace/ }).click();
    const back = page.getByRole('dialog');
    await back.getByLabel('Email address').fill(email);
    await back.getByLabel('Password').fill(PASSWORD);
    await back.getByRole('button', { name: 'Sign in' }).click();
    await expect(back).toBeHidden();
    await expect(page.getByText('Browser workspace').first()).toBeVisible();
  });

  test('an owner can invite a reviewer who joins through the emailed link', async ({ page, browser, workspace }) => {
    const email = uniqueEmail();
    await page.goto('/settings');
    const members = page.locator('.workspace-members-card');
    await members.getByLabel('Email address').fill(email);
    await members.getByLabel('Role').selectOption('reviewer');
    await members.getByRole('button', { name: 'Invite member' }).click();
    await expect(members.getByText(email)).toBeVisible();

    const message = await latestMessage('workspace_invitation');
    expect(message.to).toBe(email);
    expect(message.body).toContain('/accept-invitation#token=');
    const token = await tokenFrom('workspace_invitation');
    const inviteeContext = await browser.newContext({ baseURL: new URL(page.url()).origin });
    const invitee = await inviteeContext.newPage();
    await invitee.goto(`/accept-invitation#token=${token}`);
    await invitee.getByLabel('Your name').fill('Browser reviewer');
    await invitee.getByLabel('Password').fill(PASSWORD);
    await invitee.getByRole('button', { name: 'Join workspace' }).click();
    await expect(invitee).toHaveURL(/\/$/);
    await expect(invitee.getByText('Browser reviewer').first()).toBeVisible();

    await page.reload();
    const role = page.getByLabel(`Role for ${email}`);
    await expect(role).toHaveValue('reviewer');
    await role.selectOption('viewer');
    await expect(role).toHaveValue('viewer');
    expect(workspace.workspace).toBe('E2E workspace');
    await inviteeContext.close();
  });

  test('a wrong password is reported without revealing whether the account exists', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /My workspace/ }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Email address').fill('definitely-not-registered@example.test');
    await dialog.getByLabel('Password').fill('a-wrong-password-here');
    await dialog.getByRole('button', { name: 'Sign in' }).click();
    await expect(dialog.getByRole('alert')).toHaveText('Email or password is incorrect.');
    await expect(dialog).toBeVisible();
  });

  test('an expired session cannot leave workspace records on screen', async ({ page, workspace }) => {
    await page.goto('/discover');
    await expect(page.getByRole('heading', { name: /Discover your next opportunity/ })).toBeVisible();

    // Drop the session the way an expiry or a sign-out in another tab would.
    await page.context().clearCookies();
    await page.reload();

    await expect(page.getByRole('button', { name: /My workspace/ })).toBeVisible();
    await expect(page.locator('.product-card')).toHaveCount(0);
    expect(workspace.email).toContain('@');
  });

  test('a session that expires while the page is open clears the records it had loaded', async ({ page, workspace }) => {
    await captureAndConfirm(page, asin(41), 'Loaded before expiry');
    await page.goto('/discover');
    await expect(page.locator('.product-card')).toHaveCount(1);

    // No reload: the cookie disappears under a page that is already showing records, and
    // the user keeps navigating inside the single-page app.
    await page.context().clearCookies();
    // Opening the investigation reads it by id, and that request is what discovers the
    // session is gone. The handler then clears every cached record, not just this one.
    await page.getByRole('link', { name: /Loaded before expiry/ }).click();

    await expect(page.getByRole('dialog')).toBeVisible();
    await page.getByRole('button', { name: 'Close dialog' }).click();
    await page.getByRole('link', { name: 'Discover', exact: true }).click();
    await expect(page.locator('.product-card')).toHaveCount(0);
    expect(workspace.email).toContain('@');
  });

  test('signing out clears the workspace without a page reload', async ({ page, workspace }) => {
    await captureAndConfirm(page, asin(42), 'Loaded before sign-out');
    await page.goto('/discover');
    await expect(page.locator('.product-card')).toHaveCount(1);

    await page.goto('/settings');
    await page.getByRole('button', { name: /Sign out/ }).click();
    await expect(page.getByRole('button', { name: /My workspace/ })).toBeVisible();
    // No dialog is forced open: signing out is deliberate, not an interruption.
    await expect(page.getByRole('dialog')).toHaveCount(0);

    await page.getByRole('link', { name: 'Discover' }).click();
    await expect(page.locator('.product-card')).toHaveCount(0);
    expect(workspace.email).toContain('@');
  });

  test('an oversized request is refused by the API', async ({ page, workspace }) => {
    // The application enforces this itself; it does not rely on the proxy in front of it.
    const response = await page.request.post('/api/v1/quotes', {
      headers: { 'X-Requested-With': 'TrendSell' },
      data: { product_id: 'x', supplier: 'y'.repeat(40000), source_url: 'https://example.com/q',
              unit_price_usd: 1, moq: 1, lead_days: 1, quote_date: '2026-09-01' },
    });
    expect(response.status()).toBe(413);
    expect(workspace.email).toContain('@');
  });
});

import { expect, test, PASSWORD, uniqueEmail } from './fixtures';

/** Registration, sign-in, sign-out and an expired session (action plan T02). */
test.describe('account access', () => {
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
    await expect(page.getByRole('article')).toHaveCount(0);
    expect(workspace.email).toContain('@');
  });
});

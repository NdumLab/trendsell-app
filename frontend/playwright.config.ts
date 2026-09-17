import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

/** Browser tests run against a disposable stack, never a developer's workspace (action plan T02).
 *
 *  Review finding 14: `npm run test:e2e -- --list` used to load the Vitest files under
 *  Playwright, throw configuration errors and discover zero browser tests. The two runners
 *  now have separate directories — Vitest owns `src/**\/*.test.ts`, Playwright owns
 *  `e2e/**\/*.spec.ts` — so each discovers only its own.
 *
 *  Each run gets its own SQLite file in a fresh temp directory and its own API process, so
 *  nothing here can read or write a real workspace.
 */
const API_PORT = Number(process.env.TRENDSELL_E2E_API_PORT ?? 8123);
const WEB_PORT = Number(process.env.TRENDSELL_E2E_WEB_PORT ?? 4173);
const ORIGIN = `http://127.0.0.1:${WEB_PORT}`;
/** One disposable directory for the whole run, shared with the worker processes.
 *
 *  This config module is loaded again in every worker, so creating the directory
 *  unconditionally would give each worker its own — and a test looking for the mail the
 *  server wrote would read an empty directory that nothing writes to. Creating it once
 *  and passing the path through the environment is what keeps them the same directory. */
const RUN_DIR = process.env.TRENDSELL_E2E_RUN_DIR ?? mkdtempSync(join(tmpdir(), 'trendsell-e2e-'));
process.env.TRENDSELL_E2E_RUN_DIR = RUN_DIR;
const DATABASE = join(RUN_DIR, 'e2e.db');
const DELETION_REGISTER = join(RUN_DIR, 'deletions');
/** The local mail sink, so the browser can exercise the flows that carry a token —
 *  password reset, email verification and invitations — exactly as a person would: by
 *  reading the token out of the message that was sent, not out of the database. The sink
 *  is test-only and must never be set in production. */
const MAIL_DIR = join(RUN_DIR, 'mail');
process.env.TRENDSELL_E2E_MAIL_DIR = MAIL_DIR;
// The repository venv when it exists, so a local run needs no extra setup; plain `python` in CI.
const PYTHON = process.env.TRENDSELL_E2E_PYTHON ?? '../.venv/bin/python';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  // Kept outside the Vite project root's watched sources: writing traces under src/ or
  // e2e/ makes the dev server hot-reload mid-test.
  outputDir: './.playwright/artifacts',
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  reporter: process.env.CI ? [['list'], ['html', { open: 'never', outputFolder: './.playwright/report' }]] : [['list']],
  use: {
    baseURL: ORIGIN,
    // Failure artifacts are kept, and carry no credentials: the fixtures use throwaway
    // accounts, and the session cookie is HttpOnly so it never reaches a trace snapshot.
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `${PYTHON} -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port ${API_PORT}`,
      cwd: '../backend',
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: false,
      stdout: 'pipe',
      stderr: 'pipe',
      env: {
        APP_ENV: 'test',
        DATABASE_URL: `sqlite:///${DATABASE}`,
        CORS_ORIGINS: `${ORIGIN},http://localhost:${WEB_PORT}`,
        ALLOW_REGISTRATION: 'true',
        RESEARCH_DAILY_LIMIT: '1000',
        // Each browser test signs into its own throwaway workspace, which the shipped
        // per-address limits would (correctly) stop. test_request_limits.py covers them.
        REGISTER_IP_HOURLY_LIMIT: '500',
        LOGIN_IP_HOURLY_LIMIT: '500',
        // large-workspace.spec.ts seeds several hundred records to prove the list screens
        // are not capped at one page (review finding R10). The shipped write limit is a
        // deliberate throttle on exactly that; test_request_limits.py covers it directly.
        WORKSPACE_WRITE_MINUTE_LIMIT: '5000',
        DELETION_REGISTER_DIR: DELETION_REGISTER,
        MAIL_TRANSPORT: 'sink',
        MAIL_SINK_DIR: MAIL_DIR,
      },
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: ORIGIN,
      reuseExistingServer: false,
      stdout: 'pipe',
      stderr: 'pipe',
      env: { TRENDSELL_API_URL: `http://127.0.0.1:${API_PORT}` },
    },
  ],
});

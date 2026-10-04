import { defineConfig } from 'vitest/config';
import { fileURLToPath, URL } from 'node:url';
export default defineConfig({
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  // Vitest owns src/**/*.test.ts; Playwright owns e2e/**/*.spec.ts (action plan T02).
  test: { environment: 'node', include: ['src/**/*.test.ts'], exclude: ['e2e/**', 'node_modules/**', 'dist/**'], reporters: ['default'] },
});

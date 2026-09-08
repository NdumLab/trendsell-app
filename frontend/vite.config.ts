import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
// Browser tests start their own API on a throwaway port (see playwright.config.ts).
const api = process.env.TRENDSELL_API_URL || 'http://127.0.0.1:8001';
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: { proxy: { '/api': api }, watch: { ignored: ['**/.playwright/**'] } },
  preview: { proxy: { '/api': api } },
  build: { outDir: 'dist' },
});

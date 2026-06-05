//genai: Sprint 6 follow-up — Vitest config for web unit tests.
import path from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  // Mirror tsconfig.json's `@/*` alias so test imports look like runtime ones.
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  test: {
    // jsdom gives us a DOM in node so React components can mount.
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    // Vitest also picks up node_modules tests by default — exclude.
    exclude: ['node_modules', '.next', 'tests/e2e/**'],
    css: false,
    coverage: {
      reporter: ['text', 'html'],
      include: ['lib/**/*.ts', 'components/**/*.tsx'],
      exclude: [
        // `'server-only'` modules can't be unit-tested here; covered by E2E.
        'lib/api.ts',
        'lib/auth.ts',
        'lib/session.ts',
      ],
    },
  },
})

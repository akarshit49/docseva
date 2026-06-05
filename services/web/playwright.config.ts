//genai: Sprint 6 follow-up — Playwright config.
//
// Targets the full nginx-fronted stack at PW_BASE_URL (defaults to
// http://localhost). Run `docker-compose up -d` before `npm run test:e2e`.
import { defineConfig, devices } from '@playwright/test'

const BASE_URL = process.env.PW_BASE_URL || 'http://localhost'

export default defineConfig({
  testDir: './tests/e2e',
  // Each spec spins up its own browser context — keep them isolated.
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})

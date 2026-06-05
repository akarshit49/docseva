//genai: Sprint 6 follow-up — full anchor-flow happy path E2E (web channel).
//
// This is the critical-path test from EXECUTION_PLAN_MULTI_CHANNEL.md §19:
// "Anchor flow (sign up → upload → confirm → generate → download)".
//
// Prereqs to run this test:
//   1. `docker-compose up -d` so the API + MinIO + Redis + Next stack is live.
//   2. EMAIL_PROVIDER=log (default in .env.example) — the test reads the OTP
//      out of the api container logs.
//   3. PW_BASE_URL pointing at the nginx-fronted address (default localhost).
//
// The spec is intentionally skipped when the env var PW_RUN_E2E_FULL is not
// set, because it touches the real DB + storage and we don't want it baked
// into the lightweight CI smoke run.
import { execSync } from 'node:child_process'
import path from 'node:path'

import { expect, test } from '@playwright/test'

const FULL = process.env.PW_RUN_E2E_FULL === '1'
const FIXTURE_PDF = path.resolve(__dirname, './fixtures/supplier-quote.pdf')

test.describe('anchor flow', () => {
  test.skip(
    !FULL,
    'set PW_RUN_E2E_FULL=1 to run; needs docker-compose up + a seeded fixture PDF',
  )

  test('drop → confirm → format → download', async ({ page }) => {
    const email = `e2e+${Date.now()}@docseva.test`

    // ── 1. Login (email OTP via the "log" provider — OTP comes from logs) ──
    await page.goto('/login')
    await page.getByLabel(/email/i).fill(email)
    await page.getByRole('button', { name: /send code|continue/i }).click()
    // Wait for the OTP field to appear (the request-otp roundtrip is < 2s).
    await expect(page.getByLabel(/code|otp/i)).toBeVisible({ timeout: 10_000 })

    // Read the OTP out of the API container logs. `docker-compose logs api`
    // includes lines like:  "OTP for foo@bar.test: 123456".
    const logs = execSync('docker-compose logs --no-color --tail=200 api', {
      encoding: 'utf8',
    })
    const match = logs.match(new RegExp(`OTP for ${email}: (\\d{6})`))
    if (!match) throw new Error(`No OTP found in API logs for ${email}`)
    const otp = match[1]

    await page.getByLabel(/code|otp/i).fill(otp)
    await page.getByRole('button', { name: /verify|sign in|continue/i }).click()
    await expect(page).toHaveURL(/\/dashboard$/)

    // ── 2. Anchor flow ───────────────────────────────────────────────────
    await page.goto('/new-quote')
    await page.setInputFiles('input[type=file]', FIXTURE_PDF)
    // Step 2 — preview must be visible within 15s.
    await expect(page.getByText(/confirm|items|recipient/i)).toBeVisible({
      timeout: 15_000,
    })

    await page
      .getByRole('button', { name: /continue|next|format/i })
      .first()
      .click()
    // Step 3 — format picker. We pick the default (no saved format yet).
    await page.getByRole('button', { name: /generate|create|finish/i }).click()

    // Step 4 — download link appears.
    const download = page.getByRole('link', { name: /download/i }).first()
    await expect(download).toBeVisible({ timeout: 30_000 })
    const href = await download.getAttribute('href')
    expect(href).toMatch(/^https?:\/\//)
  })
})

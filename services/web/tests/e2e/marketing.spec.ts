//genai: Sprint 6 follow-up — public marketing pages render without auth.
//
// These are the entry-most pages a dealer sees before signing up. Catching a
// crash here would block the entire funnel, so they're our cheapest smoke
// test post-deploy.
import { expect, test } from '@playwright/test'

test.describe('Marketing surface', () => {
  test('landing page shows the anchor flow CTA', async ({ page }) => {
    await page.goto('/')
    // We don't lock to exact copy (it'll change) — just the anchor metaphor.
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(
      page.getByRole('link', { name: /get started|start|sign in/i }).first(),
    ).toBeVisible()
  })

  test('login page shows the email field + Send code button', async ({ page }) => {
    await page.goto('/login')
    await expect(
      page.getByPlaceholder(/email|you@/i).or(page.getByLabel(/email/i)),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: /send code|continue|sign in/i }),
    ).toBeVisible()
  })

  test('pricing page renders plan tiers', async ({ page }) => {
    await page.goto('/pricing')
    // The Vertical spec calls out Free / Starter / Pro / Business — at least
    // two of those words should appear somewhere on the page.
    const body = await page.textContent('body')
    const tierMatches = ['Free', 'Starter', 'Pro', 'Business'].filter((t) =>
      (body || '').includes(t),
    )
    expect(tierMatches.length).toBeGreaterThanOrEqual(2)
  })
})

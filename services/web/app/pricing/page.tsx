//genai: Sprint 3 / WS-G — Pricing page.
import Link from 'next/link'
import { Check } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Logo } from '@/components/shared/logo'

export const metadata = { title: 'Pricing' }

const TIERS = [
  {
    name: 'Free',
    price: '₹0',
    cadence: '/month',
    docs: '10 documents / month',
    cta: { label: 'Start free', href: '/login' },
    primary: false,
    bullets: [
      'Sister Quotation',
      'Quotation Comparison',
      'GST Validator',
      'Quote → Invoice',
      'Email support',
    ],
  },
  {
    name: 'Starter',
    price: '₹499',
    cadence: '/month',
    docs: '100 documents / month',
    cta: { label: 'Choose Starter', href: '/login' },
    primary: true,
    bullets: [
      'Everything in Free',
      'Saved tender formats',
      'Telegram + WhatsApp channels',
      'History + re-download',
      'Priority support',
    ],
  },
  {
    name: 'Pro',
    price: '₹1,499',
    cadence: '/month',
    docs: '500 documents / month',
    cta: { label: 'Choose Pro', href: '/login' },
    primary: false,
    bullets: [
      'Everything in Starter',
      'Multi-user team (Phase 2)',
      'Custom branding',
      'Bulk operations',
      'Phone support',
    ],
  },
]

export default function PricingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="border-b border-ink-100">
        <div className="container flex h-16 items-center justify-between">
          <Link href="/">
            <Logo />
          </Link>
          <Link href="/login">
            <Button size="sm">Sign in</Button>
          </Link>
        </div>
      </header>
      <main className="container flex-1 py-16">
        <div className="mx-auto max-w-2xl text-center">
          <h1 className="text-3xl font-semibold text-ink-900 sm:text-4xl">Simple, dealer-friendly pricing</h1>
          <p className="mt-4 text-ink-500">
            Pay only when you scale past the free tier. Cancel anytime — your saved templates stay yours.
          </p>
        </div>
        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {TIERS.map((tier) => (
            <div
              key={tier.name}
              className={`rounded-2xl border bg-white p-8 shadow-card ${
                tier.primary ? 'border-brand ring-2 ring-brand/20' : 'border-ink-100'
              }`}
            >
              <h3 className="text-sm font-semibold uppercase tracking-wide text-ink-500">
                {tier.name}
              </h3>
              <div className="mt-2 flex items-baseline gap-1">
                <span className="text-4xl font-semibold text-ink-900">{tier.price}</span>
                <span className="text-ink-500">{tier.cadence}</span>
              </div>
              <p className="mt-1 text-sm text-ink-500">{tier.docs}</p>
              <ul className="mt-6 space-y-3 text-sm text-ink-700">
                {tier.bullets.map((b) => (
                  <li key={b} className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 flex-none text-success" aria-hidden />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
              <Link href={tier.cta.href} className="mt-8 block">
                <Button block variant={tier.primary ? 'primary' : 'outline'}>
                  {tier.cta.label}
                </Button>
              </Link>
            </div>
          ))}
        </div>
        <p className="mt-10 text-center text-xs text-ink-500">
          Need a higher plan or invoiced billing? Email{' '}
          <a href="mailto:sales@docseva.in" className="text-brand">
            sales@docseva.in
          </a>
          .
        </p>
      </main>
    </div>
  )
}

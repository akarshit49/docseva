//genai: Sprint 3 / WS-G — Public landing page (anchor-first).
//
// Single-page hero that lasers in on the headline promise. No 12-feature grid.
// Toolkit and utilities live behind /pricing + /tools (the latter is behind auth).
import Link from 'next/link'
import {
  ArrowRight,
  CheckCircle2,
  FileSpreadsheet,
  Scale,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Logo } from '@/components/shared/logo'

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="sticky top-0 z-30 border-b border-ink-100 bg-white/80 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <Logo />
          <nav className="flex items-center gap-2">
            <Link href="/pricing" className="hidden text-sm text-ink-700 hover:text-ink-900 sm:inline">
              Pricing
            </Link>
            <Link href="/login">
              <Button variant="ghost" size="sm">
                Sign in
              </Button>
            </Link>
            <Link href="/login">
              <Button size="sm">Get started</Button>
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="container py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <p className="mb-4 inline-flex items-center gap-2 rounded-full bg-brand-soft px-3 py-1 text-xs font-medium text-brand">
              <span>Built for instrument & equipment dealers</span>
            </p>
            <h1 className="text-4xl font-semibold tracking-tight text-ink-900 sm:text-5xl">
              Supplier quote → your branded customer quote{' '}
              <span className="text-brand">in under 2 minutes.</span>
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-ink-500">
              DocSeva is the operating system for dealers, traders, and manufacturers of
              scientific, lab, industrial, medical and electrical instruments. Drop a
              supplier's PDF, confirm the items, and download a polished quote in your
              tender format. No copy-paste. No re-typing.
            </p>
            <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
              <Link href="/login">
                <Button size="lg">
                  Try it free
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </Button>
              </Link>
              <Link href="/pricing">
                <Button size="lg" variant="outline">
                  See pricing
                </Button>
              </Link>
            </div>
            <p className="mt-4 text-xs text-ink-500">
              Free plan includes 10 documents / month. No credit card required.
            </p>
          </div>
        </section>

        {/* Toolkit strip — Tier 2 features as social proof of completeness */}
        <section className="border-y border-ink-100 bg-ink-100/60 py-10">
          <div className="container">
            <p className="mb-6 text-center text-xs font-medium uppercase tracking-wide text-ink-500">
              Toolkit that comes with it
            </p>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <FeaturePill icon={Scale} title="Comparison" subtitle="2–10 supplier quotes side-by-side" />
              <FeaturePill icon={ShieldCheck} title="GST Validator" subtitle="Sanity-check any invoice" />
              <FeaturePill icon={FileSpreadsheet} title="Quote → Invoice" subtitle="One-click conversion" />
              <FeaturePill icon={CheckCircle2} title="Saved formats" subtitle="Use your own tender layouts" />
            </div>
          </div>
        </section>

        {/* Three-step explainer */}
        <section className="container py-20">
          <h2 className="text-center text-2xl font-semibold text-ink-900 sm:text-3xl">
            Three steps, every time.
          </h2>
          <div className="mt-10 grid gap-6 sm:grid-cols-3">
            <Step n={1} title="Drop a supplier quote" body="PDF, DOC, DOCX, or even a photo of a paper quote." />
            <Step
              n={2}
              title="Confirm what we read"
              body="An editable table of items, prices, and HSN. You own the data before it becomes a PDF."
            />
            <Step
              n={3}
              title="Download your branded quote"
              body="In the tender format you saved earlier. Optionally adjust prices with one tap."
            />
          </div>
        </section>
      </main>

      <footer className="border-t border-ink-100 bg-white">
        <div className="container flex flex-col items-center justify-between gap-4 py-8 text-sm text-ink-500 sm:flex-row">
          <Logo compact />
          <nav className="flex items-center gap-5">
            <Link href="/pricing">Pricing</Link>
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
          </nav>
          <p>© {new Date().getFullYear()} DocSeva</p>
        </div>
      </footer>
    </div>
  )
}

function FeaturePill({
  icon: Icon,
  title,
  subtitle,
}: {
  icon: LucideIcon
  title: string
  subtitle: string
}) {
  return (
    <div className="rounded-xl border border-ink-100 bg-white px-4 py-3">
      <Icon className="h-5 w-5 text-brand" aria-hidden />
      <p className="mt-2 text-sm font-medium text-ink-900">{title}</p>
      <p className="text-xs text-ink-500">{subtitle}</p>
    </div>
  )
}

function Step({ n, title, body }: { n: number; title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-card">
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-soft text-sm font-semibold text-brand">
        {n}
      </div>
      <h3 className="mt-4 text-lg font-semibold text-ink-900">{title}</h3>
      <p className="mt-2 text-sm text-ink-500">{body}</p>
    </div>
  )
}

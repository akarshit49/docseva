//genai: Sprint 3 / WS-G — Terms stub.
import Link from 'next/link'

import { Logo } from '@/components/shared/logo'

export const metadata = { title: 'Terms of Service' }

export default function TermsPage() {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="border-b border-ink-100">
        <div className="container flex h-16 items-center">
          <Link href="/">
            <Logo />
          </Link>
        </div>
      </header>
      <main className="container max-w-3xl py-16">
        <h1 className="text-3xl font-semibold text-ink-900">Terms of Service</h1>
        <p className="mt-4 text-ink-500">Last updated: 1 June 2026.</p>
        <section className="prose mt-8 space-y-4 text-ink-700">
          <p>
            By using DocSeva you agree to the following terms. This is a working copy —
            consult counsel before publishing in production.
          </p>
          <h2 className="text-lg font-semibold text-ink-900">1. The service</h2>
          <p>
            DocSeva turns supplier quotations into your branded customer quotations and
            performs a number of related document-processing tasks. We make a reasonable
            effort to keep the service available but do not promise 100% uptime.
          </p>
          <h2 className="text-lg font-semibold text-ink-900">2. Your data</h2>
          <p>
            You retain ownership of every document you upload and every document we
            generate for you. Account deletion removes both.
          </p>
          <h2 className="text-lg font-semibold text-ink-900">3. Acceptable use</h2>
          <p>
            Don't upload anything you don't have the right to process. Don't try to
            reverse-engineer the service or abuse our LLM credits via automated batch
            ingestion outside our published rate limits.
          </p>
          <h2 className="text-lg font-semibold text-ink-900">4. Disputes</h2>
          <p>Indian law applies. Disputes are resolved in the courts of Bengaluru.</p>
        </section>
      </main>
    </div>
  )
}

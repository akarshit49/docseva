//genai: Sprint 3 / WS-G — Privacy stub (DPDP-ready copy).
import Link from 'next/link'

import { Logo } from '@/components/shared/logo'

export const metadata = { title: 'Privacy' }

export default function PrivacyPage() {
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
        <h1 className="text-3xl font-semibold text-ink-900">Privacy</h1>
        <p className="mt-4 text-ink-500">Last updated: 1 June 2026.</p>
        <section className="prose mt-8 space-y-4 text-ink-700">
          <p>
            DocSeva ("we") is a multi-tenant document automation service. We collect only
            what we need to operate the service: your name, business name, business contact
            details, the documents you upload, and the documents we generate for you.
          </p>
          <p>
            We do not sell your data. We do not train third-party AI models on your
            documents. AI calls are stateless and contractually retain no inputs.
          </p>
          <p>
            Document retention is configurable per account (default 30 days). You can
            request a complete export of your data or full deletion of your account at
            any time from Settings → Account.
          </p>
          <p>
            We are committed to the Digital Personal Data Protection Act, 2023.
          </p>
          <p>
            Questions? Email{' '}
            <a href="mailto:privacy@docseva.in" className="text-brand">
              privacy@docseva.in
            </a>
            .
          </p>
        </section>
      </main>
    </div>
  )
}

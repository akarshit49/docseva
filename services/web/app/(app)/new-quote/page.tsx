//genai: Sprint 3 / WS-H — Anchor flow entry point. Server fetches saved formats
//        so the client can render step 3 instantly without a follow-up XHR.
import { NewQuoteWizard } from './wizard'
import { listSisterFormats } from '@/lib/api'
import { requireMe } from '@/lib/auth'

export const metadata = { title: 'New quote' }

export default async function NewQuotePage() {
  await requireMe()
  const formats = await listSisterFormats().catch(() => [])
  return (
    <div className="mx-auto max-w-wizard">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-900">New quote</h1>
        <p className="text-sm text-ink-500">
          Supplier quote → your branded customer quote in 4 steps.
        </p>
      </div>
      <NewQuoteWizard formats={formats} />
    </div>
  )
}

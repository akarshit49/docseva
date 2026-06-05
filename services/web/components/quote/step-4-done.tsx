//genai: Sprint 3 / WS-H — Step 4: download + next-action chips.
'use client'

import Link from 'next/link'
import { ArrowRight, CheckCircle2, Download, FilePlus2, Receipt } from 'lucide-react'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useNewQuoteStore } from '@/lib/store/new-quote-store'

export function Step4Done() {
  const result = useNewQuoteStore((s) => s.result)
  const reset = useNewQuoteStore((s) => s.reset)

  if (!result) {
    return (
      <Alert tone="warning">
        Hmm — we don't have a generated quote on this device. Start a new one to try again.
      </Alert>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <span className="inline-flex items-center gap-2 text-success">
            <CheckCircle2 className="h-5 w-5" aria-hidden /> Your quote is ready
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="rounded-xl border border-ink-100 bg-ink-100/40 px-4 py-3">
          <p className="text-sm font-medium text-ink-900">
            {result.output_filename || 'quote.docx'}
          </p>
          {result.quota ? (
            <p className="mt-1 text-xs text-ink-500">
              You've used {result.quota.used} of {result.quota.limit} documents this cycle.
            </p>
          ) : null}
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {result.output_url ? (
            <Link href={result.output_url} target="_blank" rel="noreferrer">
              <Button block>
                <Download className="h-4 w-4" aria-hidden /> Download
              </Button>
            </Link>
          ) : null}
          <Link href="/new-quote" onClick={() => reset()}>
            <Button variant="outline" block>
              <FilePlus2 className="h-4 w-4" aria-hidden /> Make another
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Button>
          </Link>
        </div>

        {result.document_id ? (
          <div className="rounded-xl border border-ink-100 p-4">
            <p className="text-sm font-medium text-ink-900">Next steps</p>
            <p className="mt-1 text-xs text-ink-500">
              Won the order? Convert this quote into a GST invoice in one tap.
            </p>
            <div className="mt-3">
              <Link href={`/tools/convert?source_id=${result.document_id}&to=invoice`}>
                <Button size="sm" variant="secondary">
                  <Receipt className="h-4 w-4" aria-hidden /> Convert to invoice
                </Button>
              </Link>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

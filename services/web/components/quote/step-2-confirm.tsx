//genai: Sprint 3 / WS-H — Step 2: confirm the extracted items.
'use client'

import * as React from 'react'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { ItemsEditor } from '@/components/quote/items-editor'
import type { QuotePreview } from '@/lib/types'
import { useNewQuoteStore } from '@/lib/store/new-quote-store'

const EMPTY_PREVIEW: QuotePreview = {
  recipient_name: '',
  recipient_address_lines: [],
  subject: '',
  ref_no: '',
  date: '',
  valid_until: '',
  sections: [{ name: 'GENERAL', items: [] }],
  subtotal: 0,
}

export function Step2Confirm() {
  const preview = useNewQuoteStore((s) => s.preview)
  const setPreview = useNewQuoteStore((s) => s.setPreview)
  const setStep = useNewQuoteStore((s) => s.setStep)
  const errorMessage = useNewQuoteStore((s) => s.errorMessage)

  const value = preview ?? EMPTY_PREVIEW
  const empty = (value.sections?.[0]?.items?.length ?? 0) === 0

  const update = (next: QuotePreview) => setPreview(next, next as unknown as Record<string, unknown>)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Step 2 of 4 · Confirm the extracted items</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
        {empty ? (
          <Alert tone="warning" title="No items found">
            We couldn't read items from this file. Add them manually below — you can still
            generate a branded quote.
          </Alert>
        ) : null}
        <ItemsEditor preview={value} onChange={update} />
      </CardContent>
      <CardFooter className="justify-between">
        <Button variant="ghost" onClick={() => setStep(1)}>
          ← Back
        </Button>
        <Button onClick={() => setStep(3)}>Continue →</Button>
      </CardFooter>
    </Card>
  )
}

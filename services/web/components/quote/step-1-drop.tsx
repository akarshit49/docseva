//genai: Sprint 3 / WS-H — Step 1: drop the supplier quote.
'use client'

import * as React from 'react'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Dropzone } from '@/components/ui/dropzone'
import type { QuotePreview } from '@/lib/types'
import { useNewQuoteStore } from '@/lib/store/new-quote-store'

export function Step1Drop() {
  const file = useNewQuoteStore((s) => s.file)
  const setFile = useNewQuoteStore((s) => s.setFile)
  const setPreview = useNewQuoteStore((s) => s.setPreview)
  const setStep = useNewQuoteStore((s) => s.setStep)
  const setWorking = useNewQuoteStore((s) => s.setWorking)
  const setError = useNewQuoteStore((s) => s.setError)
  const isWorking = useNewQuoteStore((s) => s.isWorking)
  const errorMessage = useNewQuoteStore((s) => s.errorMessage)

  async function handleContinue() {
    if (!file) return
    setWorking(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('mode', 'preview')
      const resp = await fetch('/api/proxy/api/v1/process/sister_quote', {
        method: 'POST',
        body: fd,
      })
      const body = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        throw new Error(
          body?.detail?.user_message ||
            body?.user_message ||
            'We couldn\'t read your file. Try a different format.',
        )
      }
      // body shape: ProcessResponse — `parsed_data` is the QuotePreview-shaped dict.
      const parsed = (body.parsed_data || {}) as Partial<QuotePreview>
      setPreview(parsed as QuotePreview, parsed as Record<string, unknown>)
      setStep(2)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setWorking(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Step 1 of 4 · Drop your supplier's quote</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}

        <Dropzone
          accept={['.pdf', '.doc', '.docx', '.xls', '.xlsx']}
          onFiles={(files) => setFile(files[0] ?? null)}
          label={file ? `Selected: ${file.name}` : 'Drag a file here or click to browse (PDF / DOC / DOCX)'}
          disabled={isWorking}
        />

        <p className="text-xs text-ink-500">
          Tip: a clear digital PDF works best. Scanned photos of paper quotes work too —
          we'll just need a moment to read them.
        </p>
      </CardContent>
      <CardFooter>
        <Button onClick={handleContinue} disabled={!file || isWorking}>
          {isWorking ? 'Reading your file…' : 'Continue →'}
        </Button>
      </CardFooter>
    </Card>
  )
}

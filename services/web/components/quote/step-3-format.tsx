//genai: Sprint 3 / WS-H — Step 3: pick a saved tender format + optional price adjust.
'use client'

import * as React from 'react'
import Link from 'next/link'
import { FileText, FolderPlus } from 'lucide-react'

import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useNewQuoteStore } from '@/lib/store/new-quote-store'
import type { SisterFormatOut } from '@/lib/types'
import { cn } from '@/lib/utils'

export function Step3Format({ formats }: { formats: SisterFormatOut[] }) {
  const file = useNewQuoteStore((s) => s.file)
  const preview = useNewQuoteStore((s) => s.preview)
  const formatId = useNewQuoteStore((s) => s.formatId)
  const outputExt = useNewQuoteStore((s) => s.outputExt)
  const priceAdjustPct = useNewQuoteStore((s) => s.priceAdjustPct)
  const setFormat = useNewQuoteStore((s) => s.setFormat)
  const setOutputExt = useNewQuoteStore((s) => s.setOutputExt)
  const setPriceAdjustPct = useNewQuoteStore((s) => s.setPriceAdjustPct)
  const setStep = useNewQuoteStore((s) => s.setStep)
  const setResult = useNewQuoteStore((s) => s.setResult)
  const setWorking = useNewQuoteStore((s) => s.setWorking)
  const setError = useNewQuoteStore((s) => s.setError)
  const isWorking = useNewQuoteStore((s) => s.isWorking)
  const errorMessage = useNewQuoteStore((s) => s.errorMessage)

  async function handleGenerate() {
    if (!file) {
      setError('We lost the source file — please go back and re-upload.')
      return
    }
    setWorking(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('mode', 'final')
      if (formatId) fd.append('format_id', formatId)
      // Pass the user-edited preview back so the server uses it verbatim,
      // plus any price adjustment + output format choice.
      fd.append(
        'params',
        JSON.stringify({
          output_extension: outputExt,
          price_adjust_pct: priceAdjustPct || 0,
          quote: preview ?? undefined,
        }),
      )
      const resp = await fetch('/api/proxy/api/v1/process/sister_quote', {
        method: 'POST',
        body: fd,
      })
      const body = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        throw new Error(
          body?.detail?.user_message ||
            body?.user_message ||
            'We couldn\'t generate the quote.',
        )
      }
      setResult(body)
      setStep(4)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setWorking(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Step 3 of 4 · Pick your format</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}

        {formats.length === 0 ? (
          <Alert tone="info" title="No saved formats yet">
            We'll use a clean default layout. To use your own tender format, upload one in{' '}
            <Link href="/library/formats" className="underline">
              Library → Formats
            </Link>{' '}
            (you can return here without losing your work).
          </Alert>
        ) : (
          <div>
            <p className="mb-3 text-sm font-medium text-ink-900">Saved formats</p>
            <ul className="grid gap-3 sm:grid-cols-2">
              <FormatTile
                selected={formatId === null}
                title="Default layout"
                subtitle="Clean, neutral layout"
                onClick={() => setFormat(null)}
              />
              {formats.map((fmt) => (
                <FormatTile
                  key={fmt.id}
                  selected={formatId === fmt.id}
                  title={fmt.name}
                  subtitle={fmt.original_filename}
                  onClick={() => setFormat(fmt.id)}
                />
              ))}
            </ul>
            <Link
              href="/library/formats"
              className="mt-3 inline-flex items-center gap-1 text-xs text-brand"
            >
              <FolderPlus className="h-3.5 w-3.5" aria-hidden /> Add another format
            </Link>
          </div>
        )}

        <fieldset className="rounded-xl border border-ink-100 p-4">
          <legend className="px-2 text-sm font-medium text-ink-900">Output</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="output_ext">File type</Label>
              <select
                id="output_ext"
                value={outputExt}
                onChange={(e) => setOutputExt(e.target.value as 'docx' | 'pdf')}
                className="h-10 w-full rounded-lg border border-ink-300 bg-white px-3 text-sm"
              >
                <option value="docx">DOCX (editable)</option>
                <option value="pdf">PDF (final)</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="price_adjust">Price adjustment %</Label>
              <Input
                id="price_adjust"
                type="number"
                step="0.1"
                value={priceAdjustPct}
                onChange={(e) => setPriceAdjustPct(Number(e.target.value) || 0)}
              />
              <p className="text-xs text-ink-500">
                Bumps every line item by this %. Use a negative number for a discount.
              </p>
            </div>
          </div>
        </fieldset>
      </CardContent>
      <CardFooter className="justify-between">
        <Button variant="ghost" onClick={() => setStep(2)} disabled={isWorking}>
          ← Back
        </Button>
        <Button onClick={handleGenerate} disabled={isWorking || !file}>
          {isWorking ? 'Generating…' : 'Generate quote →'}
        </Button>
      </CardFooter>
    </Card>
  )
}

function FormatTile({
  selected,
  title,
  subtitle,
  onClick,
}: {
  selected: boolean
  title: string
  subtitle?: string
  onClick: () => void
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={cn(
          'flex w-full items-start gap-3 rounded-xl border bg-white px-4 py-3 text-left transition-colors',
          selected ? 'border-brand ring-2 ring-brand/20' : 'border-ink-100 hover:border-ink-300',
        )}
      >
        <FileText className="mt-0.5 h-5 w-5 text-brand" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-ink-900">{title}</p>
          {subtitle ? <p className="truncate text-xs text-ink-500">{subtitle}</p> : null}
        </div>
        {selected ? <Badge tone="brand">Selected</Badge> : null}
      </button>
    </li>
  )
}

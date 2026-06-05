//genai: Sprint 4 / WS-I — numbering form.
'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'

import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { CompanyProfileOut } from '@/lib/types'

export function NumberingForm({ initial }: { initial: CompanyProfileOut | null }) {
  const router = useRouter()
  const [invoicePrefix, setInvoicePrefix] = React.useState(
    initial?.invoice_prefix ?? 'INV',
  )
  const [poPrefix, setPoPrefix] = React.useState(initial?.po_prefix ?? 'PO')
  const [quotationPrefix, setQuotationPrefix] = React.useState(
    initial?.quotation_prefix ?? 'QTN',
  )
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [success, setSuccess] = React.useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSuccess(null)
    try {
      const resp = await fetch('/api/proxy/api/v1/me/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          invoice_prefix: invoicePrefix.toUpperCase(),
          po_prefix: poPrefix.toUpperCase(),
          quotation_prefix: quotationPrefix.toUpperCase(),
        }),
      })
      if (!resp.ok) throw new Error('Could not save.')
      setSuccess('Saved.')
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      {error ? <Alert tone="danger">{error}</Alert> : null}
      {success ? <Alert tone="success">{success}</Alert> : null}

      <Row
        label="Invoice prefix"
        prefix={invoicePrefix}
        setPrefix={setInvoicePrefix}
        counter={initial?.invoice_counter ?? 0}
      />
      <Row
        label="PO prefix"
        prefix={poPrefix}
        setPrefix={setPoPrefix}
        counter={initial?.po_counter ?? 0}
      />
      <Row
        label="Quotation prefix"
        prefix={quotationPrefix}
        setPrefix={setQuotationPrefix}
        counter={initial?.quotation_counter ?? 0}
      />

      <div className="flex justify-end">
        <Button type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save changes'}
        </Button>
      </div>
    </form>
  )
}

function Row({
  label,
  prefix,
  setPrefix,
  counter,
}: {
  label: string
  prefix: string
  setPrefix: (v: string) => void
  counter: number
}) {
  const example = `${prefix.toUpperCase()}-${String(counter + 1).padStart(4, '0')}`
  return (
    <div className="grid gap-3 sm:grid-cols-2 sm:items-end">
      <div className="space-y-1.5">
        <Label>{label}</Label>
        <Input value={prefix} onChange={(e) => setPrefix(e.target.value)} maxLength={8} />
      </div>
      <div className="text-xs text-ink-500">
        Current: <Badge tone="brand">{counter}</Badge> · Next number: <code>{example}</code>
      </div>
    </div>
  )
}

//genai: Convert page client form — wraps ProcessRunner with optional bill_number
//       and bill_date overrides.  The API auto-generates both when omitted, so
//       the user can just drop a file and hit "Convert" without filling anything.
'use client'

import * as React from 'react'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ProcessRunner } from '@/components/quote/process-runner'

export function ConvertForm() {
  const today = new Date().toISOString().slice(0, 10) // yyyy-mm-dd for <input type="date">

  const [billNumber, setBillNumber] = React.useState('')
  const [billDate, setBillDate] = React.useState(today)

  // Build params at render time — ProcessRunner reads the prop at submit time.
  const params: Record<string, unknown> = {}
  if (billNumber.trim()) params.bill_number = billNumber.trim()
  if (billDate) {
    // Convert yyyy-mm-dd → dd/mm/yyyy to match the API + generated PDF format.
    const [y, m, d] = billDate.split('-')
    params.bill_date = `${d}/${m}/${y}`
  }

  return (
    <ProcessRunner
      feature="bill_to_make"
      title="Quote → invoice"
      description="Promote a confirmed quotation into a GST-ready invoice PDF."
      accept={['.pdf', '.doc', '.docx', '.xls', '.xlsx']}
      hint="PDF / DOC / DOCX / XLS / XLSX. ≤ 15 MB."
      submitLabel="Convert"
      params={params}
      extra={
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="bill_number">
              Invoice number{' '}
              <span className="text-xs text-ink-400">(auto-generated if blank)</span>
            </Label>
            <Input
              id="bill_number"
              placeholder="INV-0001"
              value={billNumber}
              onChange={(e) => setBillNumber(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="bill_date">Invoice date</Label>
            <Input
              id="bill_date"
              type="date"
              value={billDate}
              onChange={(e) => setBillDate(e.target.value)}
            />
          </div>
        </div>
      }
    />
  )
}

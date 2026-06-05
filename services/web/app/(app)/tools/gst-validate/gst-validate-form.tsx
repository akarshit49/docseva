//genai: GST validate client wrapper — keeps renderResult (a function) on the
//       client side so it doesn't get passed across the server→client boundary.
'use client'

import { ProcessRunner } from '@/components/quote/process-runner'
import type { ProcessResponse } from '@/lib/types'

function renderResult(resp: ProcessResponse) {
  const findings =
    (resp.parsed_data as { findings?: unknown[] } | undefined)?.findings ?? []
  if (!Array.isArray(findings) || findings.length === 0) {
    return <p>No issues found — your invoice looks good!</p>
  }
  return (
    <div>
      <p className="font-medium">{findings.length} issue(s) found.</p>
      <p>Open the report below for full details.</p>
    </div>
  )
}

export function GstValidateForm() {
  return (
    <ProcessRunner
      feature="gst_validate"
      title="Validate a GST invoice"
      description="We'll flag mismatches and produce a downloadable validation report."
      accept={['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png']}
      hint="PDF, DOC, DOCX, or photo of an invoice. ≤ 15 MB."
      submitLabel="Validate invoice"
      renderResult={renderResult}
    />
  )
}

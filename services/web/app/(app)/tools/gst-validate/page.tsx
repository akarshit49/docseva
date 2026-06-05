//genai: Sprint 4 / WS-I — /tools/gst-validate.
import { ToolPageShell } from '@/components/shared/tool-page-shell'
import { requireMe } from '@/lib/auth'

import { GstValidateForm } from './gst-validate-form'

export const metadata = { title: 'GST invoice validator' }

export default async function GstValidatePage() {
  await requireMe()
  return (
    <ToolPageShell
      title="GST invoice validator"
      description="Run a single invoice through HSN, math, and format checks. Get a PDF report you can attach to your audit trail."
    >
      <GstValidateForm />
    </ToolPageShell>
  )
}

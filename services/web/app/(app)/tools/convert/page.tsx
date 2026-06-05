//genai: Sprint 4 / WS-I — /tools/convert. Quote → invoice. (PDF/DOCX format
//        conversions live here too — wired up as the bill_to_make + to_docx +
//        to_pdf features mature on the backend.)
import { ToolPageShell } from '@/components/shared/tool-page-shell'
import { requireMe } from '@/lib/auth'

import { ConvertForm } from './convert-form'

export const metadata = { title: 'Convert' }

export default async function ConvertPage() {
  await requireMe()
  return (
    <ToolPageShell
      title="Quote → invoice"
      description="Turn a confirmed quotation into a GST-ready invoice — auto-numbered from your profile."
    >
      <ConvertForm />
    </ToolPageShell>
  )
}

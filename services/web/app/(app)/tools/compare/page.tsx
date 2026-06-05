//genai: Sprint 4 / WS-I — /tools/compare.
import { ProcessRunner } from '@/components/quote/process-runner'
import { ToolPageShell } from '@/components/shared/tool-page-shell'
import { requireMe } from '@/lib/auth'

export const metadata = { title: 'Compare quotations' }

export default async function ComparePage() {
  await requireMe()
  return (
    <ToolPageShell
      title="Compare quotations"
      description="Drop 2–10 supplier quotes. We'll line them up side-by-side and tell you who's cheapest per item."
    >
      <ProcessRunner
        feature="compare"
        title="Quotation comparison"
        description="Multi-supplier price comparison with cheapest-per-line highlighting."
        accept={['.pdf', '.doc', '.docx', '.xls', '.xlsx']}
        multiple
        hint="Drop 2–10 files. ≤ 15 MB each."
        submitLabel="Compare"
      />
    </ToolPageShell>
  )
}

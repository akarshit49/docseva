//genai: /tools/bg-remove — live.
import { ToolPageShell } from '@/components/shared/tool-page-shell'
import { requireMe } from '@/lib/auth'

import { BgRemoveForm } from './bg-remove-form'

export const metadata = { title: 'Background removal' }

export default async function BgRemovePage() {
  await requireMe()
  return (
    <ToolPageShell
      title="Background removal"
      description="Clean up product photos for catalogs and listings. Powered by U-2-Net."
    >
      <BgRemoveForm />
    </ToolPageShell>
  )
}

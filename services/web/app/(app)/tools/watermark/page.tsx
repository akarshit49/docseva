//genai: /tools/watermark — live. Server page reads logo presence from the
//        authenticated /auth/me payload and hands it to the client form.
import { ToolPageShell } from '@/components/shared/tool-page-shell'
import { requireMe } from '@/lib/auth'

import { WatermarkForm } from './watermark-form'

export const metadata = { title: 'Watermark' }

export default async function WatermarkPage() {
  const me = await requireMe()
  const hasLogo = Boolean(me.company_profile?.logo_key)
  return (
    <ToolPageShell
      title="Watermark"
      description="Add a translucent logo or text watermark across any product photo. Output is a high-quality PNG."
    >
      <WatermarkForm hasLogo={hasLogo} />
    </ToolPageShell>
  )
}

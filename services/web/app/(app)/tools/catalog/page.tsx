//genai: /tools/catalog — live.
import { ToolPageShell } from '@/components/shared/tool-page-shell'
import { requireMe } from '@/lib/auth'

import { CatalogForm } from './catalog-form'

export const metadata = { title: 'Product catalog' }

export default async function CatalogPage() {
  await requireMe()
  return (
    <ToolPageShell
      title="Product catalog"
      description="Turn a single product photo and a few details into a branded one-pager PDF — perfect for WhatsApp shares or quick listings."
    >
      <CatalogForm />
    </ToolPageShell>
  )
}

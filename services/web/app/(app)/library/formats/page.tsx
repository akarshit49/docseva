//genai: Sprint 4 / WS-I — /library/formats page.
import { FileText } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { LibraryTabs } from '@/components/shared/library-tabs'
import { listSisterFormats } from '@/lib/api'
import { requireMe } from '@/lib/auth'

import { FormatsList } from './formats-list'

export const metadata = { title: 'Library · Formats' }

export default async function FormatsPage() {
  await requireMe()
  const formats = await listSisterFormats().catch(() => [])
  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-900">Library</h1>
        <p className="text-sm text-ink-500">
          Saved tender formats become the templates DocSeva uses to brand your quotes.
          Up to 10 per organization.
        </p>
      </div>
      <LibraryTabs />
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-brand" aria-hidden /> Saved formats
          </CardTitle>
        </CardHeader>
        <CardContent>
          <FormatsList initialFormats={formats} />
        </CardContent>
      </Card>
    </div>
  )
}

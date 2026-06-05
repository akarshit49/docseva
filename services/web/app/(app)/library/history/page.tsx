//genai: Sprint 4 / WS-I — /library/history page.
import Link from 'next/link'
import { Download, History } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { LibraryTabs } from '@/components/shared/library-tabs'
import { listMyDocuments } from '@/lib/api'
import { requireMe } from '@/lib/auth'
import { humanDate } from '@/lib/utils'

export const metadata = { title: 'Library · History' }

const FEATURE_LABEL: Record<string, string> = {
  sister_quote: 'Sister quotation',
  bill_to_make: 'Quote → invoice',
  compare: 'Comparison',
  gst_validate: 'GST validation',
  to_docx: 'PDF → DOCX',
  to_pdf: 'DOCX → PDF',
  watermark: 'Watermark',
  bg_remove: 'Background removal',
  catalog: 'Catalog',
  rename: 'Rename',
}

export default async function HistoryPage() {
  await requireMe()
  const docs = await listMyDocuments({ limit: 50 }).catch(() => [])

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-900">Library</h1>
        <p className="text-sm text-ink-500">
          Every document DocSeva has generated for you. Retention: 30 days (configurable
          in Settings).
        </p>
      </div>
      <LibraryTabs />

      {docs.length === 0 ? (
        <EmptyState
          icon={History}
          title="No documents yet"
          description="Once you generate your first quote, it'll show up here."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y divide-ink-100">
              {docs.map((doc) => (
                <li
                  key={doc.id}
                  className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink-900">
                      {doc.output_filename ||
                        doc.original_filename ||
                        FEATURE_LABEL[doc.feature] ||
                        doc.feature}
                    </p>
                    <p className="text-xs text-ink-500">
                      {FEATURE_LABEL[doc.feature] || doc.feature} ·{' '}
                      {humanDate(doc.created_at)}
                      {doc.expires_at ? ` · expires ${humanDate(doc.expires_at)}` : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge
                      tone={
                        doc.status === 'completed'
                          ? 'success'
                          : doc.status === 'failed'
                            ? 'danger'
                            : 'neutral'
                      }
                    >
                      {doc.status}
                    </Badge>
                    {doc.download_url ? (
                      <Link
                        href={doc.download_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-xs font-medium text-brand"
                      >
                        <Download className="h-3.5 w-3.5" aria-hidden /> Download
                      </Link>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

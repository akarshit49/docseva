//genai: Sprint 3 / WS-G — Dashboard. Anchor-first hero + recent activity +
//        smaller toolkit cards. New users see the inline setup wizard.
import Link from 'next/link'
import {
  ArrowRight,
  Compass,
  FilePlus2,
  FolderOpen,
  Hammer,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SetupWizard } from '@/components/shared/setup-wizard'
import { listMyDocuments, listSisterFormats } from '@/lib/api'
import { requireMe } from '@/lib/auth'
import { humanDate } from '@/lib/utils'

export const metadata = { title: 'Dashboard' }

export default async function DashboardPage() {
  const me = await requireMe()
  const [docs, formats] = await Promise.all([
    listMyDocuments({ limit: 5 }).catch(() => []),
    listSisterFormats().catch(() => []),
  ])

  const profile = me.company_profile
  const setupIncomplete =
    !profile?.display_name ||
    !profile?.address ||
    !profile?.logo_key ||
    formats.length === 0

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-8 flex items-end justify-between gap-2">
        <div>
          <p className="text-sm text-ink-500">
            {greet()} {me.user.name?.split(' ')[0] || ''} 👋
          </p>
          <h1 className="text-2xl font-semibold text-ink-900">
            What would you like to ship today?
          </h1>
        </div>
        <Badge tone="brand">{me.organization.plan} plan</Badge>
      </div>

      {setupIncomplete ? (
        <SetupWizard
          initialDisplayName={profile?.display_name ?? ''}
          initialAddress={profile?.address ?? ''}
          initialGstin={profile?.gstin ?? ''}
          hasLogo={Boolean(profile?.logo_key)}
          hasFormat={formats.length > 0}
        />
      ) : null}

      <Card className="mb-8 overflow-hidden border-brand/40">
        <div className="bg-gradient-to-br from-brand to-brand-hover px-6 py-8 text-white">
          <p className="text-xs font-medium uppercase tracking-wide opacity-80">
            Anchor flow
          </p>
          <h2 className="mt-2 text-2xl font-semibold sm:text-3xl">
            Supplier quote → your branded quote
          </h2>
          <p className="mt-2 max-w-2xl text-sm opacity-90">
            Drop a PDF, confirm the items, choose your format. We'll handle the rest.
          </p>
          <Link href="/new-quote" className="mt-6 inline-block">
            <Button size="lg" variant="secondary">
              <FilePlus2 className="h-4 w-4" aria-hidden /> Start a new quote
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Button>
          </Link>
        </div>
      </Card>

      <section className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            {docs.length === 0 ? (
              <p className="text-sm text-ink-500">
                No documents yet. Your first quote will appear here.
              </p>
            ) : (
              <ul className="divide-y divide-ink-100">
                {docs.map((doc) => (
                  <li
                    key={doc.id}
                    className="flex items-center justify-between gap-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink-900">
                        {doc.output_filename || doc.original_filename || doc.feature}
                      </p>
                      <p className="text-xs text-ink-500">
                        {doc.feature} · {humanDate(doc.created_at)}
                      </p>
                    </div>
                    {doc.download_url ? (
                      <Link
                        href={doc.download_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-medium text-brand"
                      >
                        Download
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-4">
              <Link href="/library/history" className="text-xs text-brand">
                View all history →
              </Link>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4">
          <SmallActionCard
            icon={Compass}
            title="Compare quotations"
            body="Pick a vendor between 2–10 supplier quotes."
            href="/tools/compare"
          />
          <SmallActionCard
            icon={ShieldCheck}
            title="Validate a GST invoice"
            body="Catch HSN, math, and format issues in seconds."
            href="/tools/gst-validate"
          />
          <SmallActionCard
            icon={FolderOpen}
            title="Library"
            body="Manage saved tender formats and past documents."
            href="/library"
          />
          <SmallActionCard
            icon={Hammer}
            title="More tools"
            body="PDF↔DOCX, watermark, background removal, and more."
            href="/tools"
          />
        </div>
      </section>
    </div>
  )
}

function SmallActionCard({
  icon: Icon,
  title,
  body,
  href,
}: {
  icon: LucideIcon
  title: string
  body: string
  href: string
}) {
  return (
    <Link href={href} className="block focus-ring rounded-2xl">
      <Card className="transition-shadow hover:shadow-md">
        <CardContent className="flex items-start gap-3 py-5">
          <span className="mt-0.5 inline-flex h-9 w-9 items-center justify-center rounded-lg bg-brand-soft text-brand">
            <Icon className="h-4 w-4" aria-hidden />
          </span>
          <div>
            <p className="text-sm font-medium text-ink-900">{title}</p>
            <p className="text-xs text-ink-500">{body}</p>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

function greet(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning,'
  if (h < 18) return 'Good afternoon,'
  return 'Good evening,'
}

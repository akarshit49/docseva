//genai: Sprint 4 / WS-I — /billing — plan + quota + upgrade CTA.
import Link from 'next/link'
import { Sparkles, Wallet } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { requireMe } from '@/lib/auth'

export const metadata = { title: 'Billing' }

export default async function BillingPage() {
  const me = await requireMe()
  const org = me.organization
  const remaining = Math.max(0, org.docs_limit_per_cycle - org.docs_used_this_cycle)
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink-900">Billing</h1>
          <p className="text-sm text-ink-500">
            You're on the <Badge tone="brand">{org.plan}</Badge> plan.
          </p>
        </div>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wallet className="h-5 w-5 text-brand" aria-hidden /> Usage this cycle
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-baseline justify-between">
            <p className="text-3xl font-semibold text-ink-900">
              {org.docs_used_this_cycle}
              <span className="text-base font-normal text-ink-500">
                {' '}
                / {org.docs_limit_per_cycle} documents
              </span>
            </p>
            <Badge tone={remaining === 0 ? 'danger' : remaining < 10 ? 'warning' : 'success'}>
              {remaining} left
            </Badge>
          </div>
          <Progress
            value={org.docs_used_this_cycle}
            max={org.docs_limit_per_cycle}
          />
          <p className="text-xs text-ink-500">
            Limits reset at the start of every billing cycle.
          </p>
        </CardContent>
      </Card>

      <Card className="border-brand/40 bg-brand-soft/30">
        <CardContent className="flex items-start gap-3 py-6">
          <Sparkles className="mt-0.5 h-5 w-5 text-brand" aria-hidden />
          <div className="flex-1">
            <p className="text-sm font-medium text-ink-900">Need more documents?</p>
            <p className="mt-1 text-sm text-ink-500">
              Upgrading is one click. Your saved formats, history, and channels all carry over.
            </p>
          </div>
          <Link href="/pricing">
            <Button>See plans</Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}

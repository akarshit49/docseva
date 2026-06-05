//genai: Sprint 3 / WS-G — top bar with org name, quota pill, avatar/logout.
//
// Quota is seeded from the SSR layout props (no flash on first render), then
// refreshed live from the API on mount and on every tab-visibility change.
// This keeps it accurate even though the layout is persistent across client-side
// navigations and wouldn't otherwise re-run requireMe().
'use client'

import * as React from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { LogOut, Menu } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Logo } from '@/components/shared/logo'

export interface TopBarProps {
  orgName: string
  userName: string
  quotaUsed: number
  quotaLimit: number
  plan: string
}

export function TopBar({
  orgName,
  userName,
  quotaUsed: initialQuotaUsed,
  quotaLimit: initialQuotaLimit,
  plan,
}: TopBarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const [busy, setBusy] = React.useState(false)
  // Seed from SSR so the first paint is correct; updated live afterwards.
  const [quotaUsed, setQuotaUsed] = React.useState(initialQuotaUsed)
  const [quotaLimit, setQuotaLimit] = React.useState(initialQuotaLimit)

  async function refreshQuota() {
    try {
      const resp = await fetch('/api/proxy/api/v1/auth/me')
      if (!resp.ok) return
      const data = (await resp.json()) as {
        organization?: { docs_used_this_cycle?: number; docs_limit_per_cycle?: number }
      }
      if (data?.organization) {
        setQuotaUsed(data.organization.docs_used_this_cycle ?? quotaUsed)
        setQuotaLimit(data.organization.docs_limit_per_cycle ?? quotaLimit)
      }
    } catch {
      // Silent — stale value is acceptable; no error shown to user.
    }
  }

  // Fetch on first mount.
  React.useEffect(() => {
    refreshQuota()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Re-fetch whenever the user navigates to a new page (pathname changes).
  React.useEffect(() => {
    refreshQuota()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname])

  // Re-fetch when the user returns to this tab after switching away.
  React.useEffect(() => {
    function onVisibility() {
      if (document.visibilityState === 'visible') refreshQuota()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const remaining = Math.max(0, quotaLimit - quotaUsed)
  const tone: 'success' | 'warning' | 'danger' =
    remaining === 0 ? 'danger' : remaining < quotaLimit * 0.2 ? 'warning' : 'success'

  async function handleLogout() {
    setBusy(true)
    try {
      await fetch('/api/auth/logout', { method: 'POST' })
    } finally {
      router.replace('/login')
      router.refresh()
    }
  }

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-ink-100 bg-white px-4 lg:px-8">
      <div className="flex items-center gap-3">
        <button
          type="button"
          className="lg:hidden"
          aria-label="Open menu"
          onClick={() => {
            const el = document.getElementById('mobile-sidebar')
            el?.classList.toggle('hidden')
          }}
        >
          <Menu className="h-5 w-5" aria-hidden />
        </button>
        <div className="lg:hidden">
          <Link href="/dashboard">
            <Logo compact />
          </Link>
        </div>
        <div className="hidden text-sm text-ink-500 sm:block">
          <p>
            Signed in as <span className="font-medium text-ink-900">{userName}</span>
          </p>
          <p className="text-xs">
            {orgName} · {plan}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Badge tone={tone} className="hidden sm:inline-flex">
          {quotaUsed} / {quotaLimit} docs
        </Badge>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          disabled={busy}
          aria-label="Sign out"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          <span className="hidden sm:inline">Sign out</span>
        </Button>
      </div>
    </header>
  )
}

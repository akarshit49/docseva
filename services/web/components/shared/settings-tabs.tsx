//genai: Sprint 4 / WS-I — left tab nav for /settings/*.
'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

import { cn } from '@/lib/utils'

const TABS = [
  { href: '/settings/profile', label: 'Company profile' },
  { href: '/settings/branding', label: 'Branding & logo' },
  { href: '/settings/bank', label: 'Bank details' },
  { href: '/settings/numbering', label: 'Numbering' },
  { href: '/settings/channels', label: 'Connected channels' },
  { href: '/settings/team', label: 'Team' },
  // #genai: Sprint 6 — DPDP "right to data" controls live here.
  { href: '/settings/account', label: 'Account & data' },
]

export function SettingsTabs() {
  const pathname = usePathname() || ''
  return (
    <aside className="w-full shrink-0 lg:w-56">
      <nav className="flex gap-1 overflow-x-auto rounded-xl border border-ink-100 bg-white p-2 lg:flex-col lg:overflow-visible">
        {TABS.map((tab) => {
          const active = pathname === tab.href
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                'whitespace-nowrap rounded-lg px-3 py-2 text-sm transition-colors',
                active
                  ? 'bg-brand-soft font-medium text-brand'
                  : 'text-ink-700 hover:bg-ink-100',
              )}
            >
              {tab.label}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}

//genai: Sprint 4 / WS-I — tab strip used by /library/* pages.
'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

import { cn } from '@/lib/utils'

const TABS = [
  { href: '/library/formats', label: 'Saved formats' },
  { href: '/library/history', label: 'History' },
]

export function LibraryTabs() {
  const pathname = usePathname() || ''
  return (
    <nav className="mb-6 flex items-center gap-1 border-b border-ink-100" aria-label="Library">
      {TABS.map((tab) => {
        const active = pathname.startsWith(tab.href)
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              '-mb-px border-b-2 px-4 py-2 text-sm transition-colors',
              active
                ? 'border-brand text-brand'
                : 'border-transparent text-ink-500 hover:text-ink-900',
            )}
          >
            {tab.label}
          </Link>
        )
      })}
    </nav>
  )
}

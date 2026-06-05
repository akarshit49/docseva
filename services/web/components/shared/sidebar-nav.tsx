//genai: Sprint 3 / WS-G — left sidebar nav for the authed shell.
'use client'

import * as React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  FilePlus2,
  FolderOpen,
  Hammer,
  LayoutDashboard,
  Settings,
  Wallet,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Logo } from '@/components/shared/logo'
import { cn } from '@/lib/utils'

const ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/library', label: 'Library', icon: FolderOpen },
  { href: '/tools', label: 'Tools', icon: Hammer },
  { href: '/billing', label: 'Billing', icon: Wallet },
  { href: '/settings', label: 'Settings', icon: Settings },
]

export function SidebarNav() {
  const pathname = usePathname() || ''
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-ink-100 bg-white p-4 lg:flex">
      <div className="px-2">
        <Link href="/dashboard">
          <Logo />
        </Link>
      </div>

      {/* Sticky anchor CTA — Plan principle 4 (anchor always one click away). */}
      <Link href="/new-quote" className="mt-6 block">
        <Button block size="lg">
          <FilePlus2 className="h-4 w-4" aria-hidden />
          New quote
        </Button>
      </Link>

      <nav className="mt-6 flex-1 space-y-1" aria-label="Primary">
        {ITEMS.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`)
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                active
                  ? 'bg-brand-soft font-medium text-brand'
                  : 'text-ink-700 hover:bg-ink-100',
              )}
            >
              <item.icon className="h-4 w-4" aria-hidden />
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="rounded-xl bg-ink-100 p-4 text-xs text-ink-700">
        <p className="font-medium text-ink-900">Tip</p>
        <p className="mt-1">
          Drop a supplier quote on <Link href="/new-quote" className="underline">/new-quote</Link>{' '}
          to feel the magic.
        </p>
      </div>
    </aside>
  )
}

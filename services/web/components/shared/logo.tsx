//genai: Sprint 3 / WS-G — wordmark used in the topbar + landing.
import * as React from 'react'
import { FileText } from 'lucide-react'

import { cn } from '@/lib/utils'

export function Logo({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn('inline-flex items-center gap-2 font-semibold text-ink-900', className)}>
      <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-brand text-brand-fg">
        <FileText className="h-4 w-4" aria-hidden />
      </span>
      {!compact ? <span className="text-lg">DocSeva</span> : null}
    </span>
  )
}

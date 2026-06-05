//genai: Sprint 3 / WS-F — slim progress indicator for the anchor wizard.
import * as React from 'react'

import { cn } from '@/lib/utils'

export function Progress({
  value,
  max = 100,
  className,
}: {
  value: number
  max?: number
  className?: string
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemax={max}
      aria-valuemin={0}
      className={cn('h-2 w-full overflow-hidden rounded-full bg-ink-100', className)}
    >
      <div
        className="h-full bg-brand transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

//genai: Sprint 3 / WS-F — slim separator line.
import * as React from 'react'

import { cn } from '@/lib/utils'

export function Separator({
  className,
  orientation = 'horizontal',
}: {
  className?: string
  orientation?: 'horizontal' | 'vertical'
}) {
  return (
    <div
      role="separator"
      className={cn(
        'bg-ink-100',
        orientation === 'horizontal' ? 'h-px w-full' : 'h-full w-px',
        className,
      )}
    />
  )
}

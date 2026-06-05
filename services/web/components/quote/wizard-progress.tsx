//genai: Sprint 3 / WS-H — slim "1 → 2 → 3 → 4" progress header.
'use client'

import * as React from 'react'
import { Check } from 'lucide-react'

import { cn } from '@/lib/utils'

const STEPS = [
  { n: 1, label: 'Drop' },
  { n: 2, label: 'Confirm' },
  { n: 3, label: 'Format' },
  { n: 4, label: 'Done' },
]

export function WizardProgress({ current }: { current: number }) {
  return (
    <ol className="mb-8 flex items-center justify-between gap-2" aria-label="Steps">
      {STEPS.map((step, idx) => {
        const status =
          step.n < current ? 'complete' : step.n === current ? 'current' : 'upcoming'
        return (
          <li key={step.n} className="flex flex-1 items-center gap-2 text-xs">
            <span
              className={cn(
                'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-medium',
                status === 'complete' && 'border-brand bg-brand text-white',
                status === 'current' && 'border-brand text-brand',
                status === 'upcoming' && 'border-ink-300 text-ink-500',
              )}
              aria-current={status === 'current' ? 'step' : undefined}
            >
              {status === 'complete' ? <Check className="h-3.5 w-3.5" /> : step.n}
            </span>
            <span
              className={cn(
                'hidden whitespace-nowrap text-xs sm:inline',
                status === 'current' ? 'font-medium text-ink-900' : 'text-ink-500',
              )}
            >
              {step.label}
            </span>
            {idx < STEPS.length - 1 ? (
              <span
                aria-hidden
                className={cn(
                  'ml-2 h-px flex-1',
                  status === 'complete' ? 'bg-brand' : 'bg-ink-300',
                )}
              />
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}

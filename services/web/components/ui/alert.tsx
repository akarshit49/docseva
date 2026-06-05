//genai: Sprint 3 / WS-F — inline status banner (errors, info, success).
import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { AlertCircle, CheckCircle2, Info, TriangleAlert } from 'lucide-react'

import { cn } from '@/lib/utils'

const alertVariants = cva(
  'flex items-start gap-3 rounded-lg border px-4 py-3 text-sm',
  {
    variants: {
      tone: {
        info: 'border-brand/30 bg-brand-soft text-brand',
        success: 'border-success/30 bg-success-soft text-success',
        warning: 'border-warning/30 bg-warning-soft text-warning',
        danger: 'border-danger/30 bg-danger-soft text-danger',
      },
    },
    defaultVariants: { tone: 'info' },
  },
)

const ICONS = {
  info: Info,
  success: CheckCircle2,
  warning: TriangleAlert,
  danger: AlertCircle,
} as const

export interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {
  title?: string
}

export function Alert({ tone = 'info', title, className, children, ...props }: AlertProps) {
  const Icon = ICONS[tone ?? 'info']
  return (
    <div className={cn(alertVariants({ tone }), className)} role="alert" {...props}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div>
        {title ? <p className="font-medium leading-tight">{title}</p> : null}
        {children ? <div className={title ? 'mt-1 text-current/80' : ''}>{children}</div> : null}
      </div>
    </div>
  )
}

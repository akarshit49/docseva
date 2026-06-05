//genai: Watermark client wrapper — mode toggle (logo/text), opacity slider,
//        size slider, optional text input. Posts to /process/watermark via the
//        authenticated proxy.
'use client'

import * as React from 'react'
import Link from 'next/link'
import { Image as ImageIcon, Type, type LucideIcon } from 'lucide-react'

import { Alert } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ProcessRunner } from '@/components/quote/process-runner'
import { cn } from '@/lib/utils'

interface WatermarkFormProps {
  hasLogo: boolean
}

type Mode = 'logo' | 'text'

export function WatermarkForm({ hasLogo }: WatermarkFormProps) {
  // Default to logo mode only if a logo is configured.
  const [mode, setMode] = React.useState<Mode>(hasLogo ? 'logo' : 'text')
  const [text, setText] = React.useState('DRAFT')
  const [opacity, setOpacity] = React.useState(30)
  const [size, setSize] = React.useState(38)

  // ProcessRunner reads params at submit time.
  const params: Record<string, unknown> = {
    mode,
    opacity: opacity / 100,
    size_fraction: size / 100,
  }
  if (mode === 'text') params.text = text.trim()

  const submitDisabled = mode === 'text' && !text.trim()

  return (
    <ProcessRunner
      feature="watermark"
      title="Add a watermark"
      description="Drop a product photo. We stamp your logo or a custom phrase across it."
      accept={['.png', '.jpg', '.jpeg', '.webp']}
      hint="PNG, JPG, or WEBP. ≤ 15 MB. Output is always PNG to preserve transparency."
      submitLabel={submitDisabled ? 'Add text first' : 'Add watermark'}
      params={params}
      extra={
        <div className="space-y-4">
          {/* Mode toggle */}
          <div>
            <Label>Watermark type</Label>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <ModeTile
                selected={mode === 'logo'}
                disabled={!hasLogo}
                onClick={() => setMode('logo')}
                icon={ImageIcon}
                title="Company logo"
                subtitle={
                  hasLogo
                    ? 'Use your uploaded brand mark'
                    : 'Upload a logo in Settings → Branding first'
                }
              />
              <ModeTile
                selected={mode === 'text'}
                onClick={() => setMode('text')}
                icon={Type}
                title="Custom text"
                subtitle='Stamp a phrase like "DRAFT" or "CONFIDENTIAL"'
              />
            </div>
            {!hasLogo ? (
              <p className="mt-2 text-xs text-ink-500">
                Tip:{' '}
                <Link href="/settings/branding" className="text-brand underline">
                  upload a logo
                </Link>{' '}
                to enable logo watermarks.
              </p>
            ) : null}
          </div>

          {/* Text input — visible in text mode only */}
          {mode === 'text' ? (
            <div className="space-y-1.5">
              <Label htmlFor="wm_text">Text</Label>
              <Input
                id="wm_text"
                value={text}
                onChange={(e) => setText(e.target.value.slice(0, 40))}
                placeholder="DRAFT"
                maxLength={40}
              />
              <p className="text-xs text-ink-500">
                Short phrases work best. Max 40 characters.
              </p>
            </div>
          ) : null}

          {/* Opacity slider */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="wm_opacity">Opacity</Label>
              <span className="text-xs font-medium text-ink-700">{opacity}%</span>
            </div>
            <input
              id="wm_opacity"
              type="range"
              min={10}
              max={100}
              step={5}
              value={opacity}
              onChange={(e) => setOpacity(Number(e.target.value))}
              className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-ink-200 accent-brand"
            />
            <p className="text-xs text-ink-500">
              Lower is more subtle. 30% is a safe default.
            </p>
          </div>

          {/* Size slider */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="wm_size">Size</Label>
              <span className="text-xs font-medium text-ink-700">{size}%</span>
            </div>
            <input
              id="wm_size"
              type="range"
              min={15}
              max={80}
              step={5}
              value={size}
              onChange={(e) => setSize(Number(e.target.value))}
              className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-ink-200 accent-brand"
            />
            <p className="text-xs text-ink-500">
              Watermark width as a fraction of the shorter image side.
            </p>
          </div>

          {/* Live preview / fallback notice */}
          {mode === 'logo' && !hasLogo ? (
            <Alert tone="info" title="No logo configured">
              The watermark will fall back to text mode using the file name as the
              label. Upload a logo to use your brand mark instead.
            </Alert>
          ) : null}
        </div>
      }
    />
  )
}

interface ModeTileProps {
  selected: boolean
  disabled?: boolean
  onClick: () => void
  icon: LucideIcon
  title: string
  subtitle: string
}

function ModeTile({
  selected,
  disabled,
  onClick,
  icon: Icon,
  title,
  subtitle,
}: ModeTileProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'flex items-start gap-3 rounded-xl border bg-white px-4 py-3 text-left transition-colors',
        selected
          ? 'border-brand ring-2 ring-brand/20'
          : 'border-ink-100 hover:border-ink-300',
        disabled && 'cursor-not-allowed opacity-60 hover:border-ink-100',
      )}
    >
      <span
        className={cn(
          'mt-0.5 inline-flex h-8 w-8 items-center justify-center rounded-lg',
          selected ? 'bg-brand-soft text-brand' : 'bg-ink-100 text-ink-500',
        )}
      >
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-ink-900">{title}</p>
        <p className="mt-0.5 text-xs text-ink-500">{subtitle}</p>
      </div>
    </button>
  )
}

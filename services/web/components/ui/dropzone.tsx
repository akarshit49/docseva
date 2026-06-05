//genai: Sprint 3 / WS-H — file drop-zone used by the anchor wizard.
'use client'

import * as React from 'react'
import { CloudUpload } from 'lucide-react'

import { bytesToMb } from '@/lib/utils'
import { cn } from '@/lib/utils'

const MAX_BYTES = 15 * 1024 * 1024

export interface DropzoneProps {
  accept?: string[]
  /** Single-file mode by default; pass true for compare-style multi-upload. */
  multiple?: boolean
  onFiles: (files: File[]) => void
  label?: string
  hint?: string
  className?: string
  disabled?: boolean
}

export function Dropzone({
  accept = ['.pdf', '.doc', '.docx'],
  multiple = false,
  onFiles,
  label = 'Drag a file here or click to browse',
  hint = `Up to ${bytesToMb(MAX_BYTES)}. Supported: ${accept.join(', ')}.`,
  className,
  disabled,
}: DropzoneProps) {
  const inputRef = React.useRef<HTMLInputElement>(null)
  const [active, setActive] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const validate = (incoming: File[]): File[] => {
    const errs: string[] = []
    const ok: File[] = []
    for (const f of incoming) {
      const ext = `.${f.name.split('.').pop()?.toLowerCase() ?? ''}`
      if (accept.length && !accept.includes(ext)) {
        errs.push(`${f.name}: type ${ext} not supported.`)
        continue
      }
      if (f.size > MAX_BYTES) {
        errs.push(`${f.name}: file is too large (${bytesToMb(f.size)} > 15 MB).`)
        continue
      }
      ok.push(f)
    }
    if (errs.length) {
      setError(errs.join(' '))
    } else {
      setError(null)
    }
    return ok
  }

  const handleFiles = (raw: FileList | null) => {
    if (!raw) return
    const ok = validate(Array.from(raw))
    if (ok.length) onFiles(multiple ? ok : [ok[0]])
  }

  return (
    <div className={cn('space-y-2', className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setActive(true)
        }}
        onDragLeave={() => setActive(false)}
        onDrop={(e) => {
          e.preventDefault()
          setActive(false)
          handleFiles(e.dataTransfer.files)
        }}
        className={cn(
          'flex w-full flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed bg-ink-100/40 px-6 py-12 text-center transition-colors',
          active
            ? 'border-brand bg-brand-soft/60'
            : 'border-ink-300 hover:border-brand hover:bg-brand-soft/30',
          disabled && 'pointer-events-none opacity-60',
        )}
      >
        <CloudUpload className="h-9 w-9 text-brand" aria-hidden />
        <div>
          <p className="text-base font-medium text-ink-900">{label}</p>
          <p className="mt-1 text-xs text-ink-500">{hint}</p>
        </div>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={accept.join(',')}
        multiple={multiple}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </div>
  )
}

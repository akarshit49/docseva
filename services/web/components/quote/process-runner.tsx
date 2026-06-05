//genai: Sprint 4 / WS-I — shared single-shot runner for tools that just
//        upload a file and download a result. Used by GST validate, compare,
//        watermark, bg-remove, etc. Keeps each tool page tiny.
'use client'

import * as React from 'react'
import Link from 'next/link'
import { Download } from 'lucide-react'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Dropzone } from '@/components/ui/dropzone'
import type { ProcessResponse } from '@/lib/types'

const IMAGE_EXTS = new Set(['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp'])

function isImageOutput(filename: string | null | undefined): boolean {
  if (!filename) return false
  const ext = filename.split('.').pop()?.toLowerCase() ?? ''
  return IMAGE_EXTS.has(ext)
}

export interface ProcessRunnerProps {
  feature: string
  title: string
  description: React.ReactNode
  accept?: string[]
  multiple?: boolean
  params?: Record<string, unknown>
  /** Custom hint string for the dropzone. */
  hint?: string
  /** Render extra inputs above the dropzone. */
  extra?: React.ReactNode
  /** Action button label. */
  submitLabel?: string
  /** When the API returns parsed_data, format it for display. */
  renderResult?: (resp: ProcessResponse) => React.ReactNode
  /**
   * Override the auto-detection of image previews. Use 'never' for tools that
   * return images but should always force a download (rare). Defaults to 'auto'.
   */
  outputPreview?: 'auto' | 'never'
}

export function ProcessRunner({
  feature,
  title,
  description,
  accept = ['.pdf', '.doc', '.docx'],
  multiple = false,
  params,
  hint,
  extra,
  submitLabel = 'Run',
  renderResult,
  outputPreview = 'auto',
}: ProcessRunnerProps) {
  const [files, setFiles] = React.useState<File[]>([])
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [result, setResult] = React.useState<ProcessResponse | null>(null)

  async function handleRun() {
    if (files.length === 0) return
    setBusy(true)
    setError(null)
    try {
      const fd = new FormData()
      if (multiple) {
        for (const f of files) fd.append('files', f)
      } else {
        fd.append('file', files[0])
      }
      if (params) fd.append('params', JSON.stringify(params))
      fd.append('mode', 'final')
      const resp = await fetch(`/api/proxy/api/v1/process/${feature}`, {
        method: 'POST',
        body: fd,
      })
      const body = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        throw new Error(
          body.detail?.user_message ||
            body.user_message ||
            'Something went wrong. Please try again.',
        )
      }
      setResult(body)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <p className="mt-1 text-sm text-ink-500">{description}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? <Alert tone="danger">{error}</Alert> : null}
        {extra}
        <Dropzone
          accept={accept}
          multiple={multiple}
          onFiles={setFiles}
          label={
            files.length > 0
              ? files.length === 1
                ? `Selected: ${files[0].name}`
                : `Selected ${files.length} files`
              : multiple
                ? 'Drop multiple files here'
                : 'Drop a file here'
          }
          hint={hint}
          disabled={busy}
        />

        {result ? (
          <Alert tone="success" title="Done">
            {renderResult ? renderResult(result) : null}

            {outputPreview === 'auto' &&
            result.output_url &&
            isImageOutput(result.output_filename) ? (
              <div className="mt-3 overflow-hidden rounded-xl border border-ink-100 bg-[url('data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2220%22%20height%3D%2220%22%3E%3Crect%20width%3D%2210%22%20height%3D%2210%22%20fill%3D%22%23f3f4f6%22%2F%3E%3Crect%20x%3D%2210%22%20y%3D%2210%22%20width%3D%2210%22%20height%3D%2210%22%20fill%3D%22%23f3f4f6%22%2F%3E%3C%2Fsvg%3E')] p-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={result.output_url}
                  alt={result.output_filename || 'Output preview'}
                  className="mx-auto max-h-96 w-auto"
                />
              </div>
            ) : null}

            {result.output_url ? (
              <div className="mt-3 flex flex-wrap gap-2">
                <Link href={result.output_url} target="_blank" rel="noreferrer">
                  <Button size="sm" variant="outline">
                    <Download className="h-4 w-4" aria-hidden /> Download
                    {result.output_filename ? ` (${result.output_filename})` : ''}
                  </Button>
                </Link>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setResult(null)
                    setError(null)
                    setFiles([])
                  }}
                >
                  Run again
                </Button>
              </div>
            ) : null}
          </Alert>
        ) : null}
      </CardContent>
      <CardFooter>
        <Button onClick={handleRun} disabled={busy || files.length === 0}>
          {busy ? 'Working…' : submitLabel}
        </Button>
      </CardFooter>
    </Card>
  )
}

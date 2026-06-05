//genai: Sprint 4 / WS-I — client-side list + upload + delete for saved formats.
'use client'

import * as React from 'react'
import { Trash2 } from 'lucide-react'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dropzone } from '@/components/ui/dropzone'
import { EmptyState } from '@/components/ui/empty-state'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { humanDate } from '@/lib/utils'
import type { SisterFormatOut } from '@/lib/types'

const MAX = 10

export function FormatsList({ initialFormats }: { initialFormats: SisterFormatOut[] }) {
  const [formats, setFormats] = React.useState<SisterFormatOut[]>(initialFormats)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [pendingFile, setPendingFile] = React.useState<File | null>(null)
  const [pendingName, setPendingName] = React.useState('')

  async function handleUpload() {
    if (!pendingFile || !pendingName.trim()) return
    setBusy(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', pendingFile)
      const resp = await fetch(
        `/api/proxy/api/v1/me/sister-formats?name=${encodeURIComponent(pendingName.trim())}`,
        { method: 'POST', body: fd },
      )
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(body.detail?.user_message || body.user_message || 'Upload failed.')
      }
      const next = (await resp.json()) as SisterFormatOut
      setFormats((prev) => [...prev, next])
      setPendingFile(null)
      setPendingName('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this format? Quotes that were already generated remain intact.')) return
    setBusy(true)
    setError(null)
    try {
      const resp = await fetch(`/api/proxy/api/v1/me/sister-formats/${id}`, { method: 'DELETE' })
      if (!resp.ok && resp.status !== 204) {
        throw new Error('Could not delete format.')
      }
      setFormats((prev) => prev.filter((f) => f.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      {error ? <Alert tone="danger">{error}</Alert> : null}

      {formats.length === 0 ? (
        <EmptyState
          title="No saved formats yet"
          description="Upload a sample of your tender format so DocSeva can brand every quote in the same style. PDF, DOC, or DOCX."
        />
      ) : (
        <ul className="divide-y divide-ink-100 rounded-xl border border-ink-100 bg-white">
          {formats.map((fmt) => (
            <li
              key={fmt.id}
              className="flex items-center justify-between gap-3 px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink-900">{fmt.name}</p>
                <p className="text-xs text-ink-500">
                  {fmt.original_filename} · added {humanDate(fmt.created_at)}
                </p>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleDelete(fmt.id)}
                disabled={busy}
                aria-label={`Delete ${fmt.name}`}
              >
                <Trash2 className="h-4 w-4" aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <fieldset className="rounded-xl border border-dashed border-ink-300 p-4">
        <legend className="px-2 text-sm font-medium text-ink-900">
          Add a new format ({formats.length} / {MAX})
        </legend>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="format_name">Display name</Label>
            <Input
              id="format_name"
              value={pendingName}
              onChange={(e) => setPendingName(e.target.value)}
              placeholder="Government tender layout"
              disabled={busy || formats.length >= MAX}
            />
          </div>
          <Dropzone
            accept={['.pdf', '.doc', '.docx']}
            onFiles={(files) => setPendingFile(files[0] ?? null)}
            label={pendingFile ? `Selected: ${pendingFile.name}` : 'Drop your format here'}
            hint="PDF, DOC, or DOCX. ≤ 15 MB."
            disabled={busy || formats.length >= MAX}
          />
          <div className="flex justify-end">
            <Button
              onClick={handleUpload}
              disabled={busy || !pendingFile || !pendingName.trim() || formats.length >= MAX}
            >
              {busy ? 'Uploading…' : 'Save format'}
            </Button>
          </div>
        </div>
      </fieldset>
    </div>
  )
}

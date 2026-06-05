//genai: Sprint 6 — client component handling Export + Delete.
'use client'

import * as React from 'react'
import { Download, Loader2, Trash2 } from 'lucide-react'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

type ExportState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'done'; bytes: number }
  | { kind: 'error'; message: string }

type DeleteState =
  | { kind: 'idle' }
  | { kind: 'confirming' }
  | { kind: 'submitting' }
  | { kind: 'done'; message: string; deletionRequestedAt: string }
  | { kind: 'error'; message: string }

export function AccountActions() {
  const [exportState, setExportState] = React.useState<ExportState>({ kind: 'idle' })
  const [deleteState, setDeleteState] = React.useState<DeleteState>({ kind: 'idle' })

  // ── Export ────────────────────────────────────────────────────────────────
  // We call the API client-side via a small fetch wrapper so the JSON download
  // can become a file the user keeps. This intentionally uses fetch (not
  // callApi) so the body can stream straight into a Blob.

  async function onExport() {
    setExportState({ kind: 'loading' })
    try {
      const res = await fetch('/api/proxy/api/v1/me/account/export', {
        method: 'GET',
        credentials: 'include',
      })
      if (!res.ok) {
        const body = await res.text().catch(() => '')
        throw new Error(body || `Export failed (${res.status})`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `docseva-export-${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setExportState({ kind: 'done', bytes: blob.size })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Export failed.'
      setExportState({ kind: 'error', message })
    }
  }

  // ── Delete ────────────────────────────────────────────────────────────────

  async function onConfirmDelete() {
    setDeleteState({ kind: 'submitting' })
    try {
      const res = await fetch('/api/proxy/api/v1/me/account/delete', {
        method: 'POST',
        credentials: 'include',
      })
      if (!res.ok) {
        const body = await res.text().catch(() => '')
        throw new Error(body || `Delete failed (${res.status})`)
      }
      const payload = (await res.json()) as {
        message: string
        deletion_requested_at: string
      }
      setDeleteState({
        kind: 'done',
        message: payload.message,
        deletionRequestedAt: payload.deletion_requested_at,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Delete failed.'
      setDeleteState({ kind: 'error', message })
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-base font-semibold text-ink-900">Export my data</h3>
            <p className="text-sm text-ink-500">
              Downloads a JSON file with your user, organization, profile,
              documents, formats and channel links.
            </p>
          </div>
          <Button onClick={onExport} disabled={exportState.kind === 'loading'}>
            {exportState.kind === 'loading' ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Download className="mr-2 h-4 w-4" aria-hidden />
            )}
            Download JSON
          </Button>
        </div>
        {exportState.kind === 'done' && (
          <Alert tone="success" className="mt-3" title="Export ready">
            Saved {(exportState.bytes / 1024).toFixed(1)} KB to your device.
          </Alert>
        )}
        {exportState.kind === 'error' && (
          <Alert tone="danger" className="mt-3" title="Couldn't export">
            {exportState.message}
          </Alert>
        )}
      </section>

      <hr className="border-ink-200" />

      <section>
        <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-base font-semibold text-ink-900">Delete my account</h3>
            <p className="text-sm text-ink-500">
              Schedule everything for permanent deletion. You&apos;ll have 30 days
              to change your mind.
            </p>
          </div>
          {deleteState.kind === 'idle' && (
            <Button
              variant="danger"
              onClick={() => setDeleteState({ kind: 'confirming' })}
            >
              <Trash2 className="mr-2 h-4 w-4" aria-hidden />
              Delete my account
            </Button>
          )}
        </div>

        {deleteState.kind === 'confirming' && (
          <div className="mt-4 rounded-lg border border-danger/30 bg-danger-soft p-4">
            <p className="text-sm text-danger">
              Are you absolutely sure? After 30 days every document, format,
              logo and channel link tied to your account will be permanently
              purged. This cannot be undone.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                variant="ghost"
                onClick={() => setDeleteState({ kind: 'idle' })}
              >
                Cancel
              </Button>
              <Button variant="danger" onClick={onConfirmDelete}>
                Yes, delete my account
              </Button>
            </div>
          </div>
        )}

        {deleteState.kind === 'submitting' && (
          <p className="mt-3 flex items-center gap-2 text-sm text-ink-500">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Submitting…
          </p>
        )}

        {deleteState.kind === 'done' && (
          <Alert tone="success" className="mt-3" title="Deletion scheduled">
            {deleteState.message}
            <span className="mt-1 block text-xs text-ink-500">
              Requested {new Date(deleteState.deletionRequestedAt).toLocaleString()}.
            </span>
          </Alert>
        )}

        {deleteState.kind === 'error' && (
          <Alert tone="danger" className="mt-3" title="Couldn't schedule deletion">
            {deleteState.message}
          </Alert>
        )}
      </section>
    </div>
  )
}

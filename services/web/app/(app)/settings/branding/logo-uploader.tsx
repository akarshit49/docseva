//genai: Sprint 4 / WS-I — small client component for logo upload.
'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dropzone } from '@/components/ui/dropzone'

export function LogoUploader() {
  const router = useRouter()
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  async function handleUpload(files: File[]) {
    const file = files[0]
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const resp = await fetch('/api/proxy/api/v1/me/profile/logo', {
        method: 'POST',
        body: fd,
      })
      if (!resp.ok) throw new Error('Logo upload failed.')
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3">
      {error ? <Alert tone="danger">{error}</Alert> : null}
      <Dropzone
        accept={['.png', '.jpg', '.jpeg', '.webp']}
        onFiles={handleUpload}
        label="Drop a logo to replace the existing one"
        hint="PNG, JPG, or WEBP. ≤ 15 MB. Square logos look best."
        disabled={busy}
      />
      <Button type="button" variant="outline" disabled>
        Coming soon: theme color picker
      </Button>
    </div>
  )
}

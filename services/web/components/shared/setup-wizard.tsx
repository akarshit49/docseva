//genai: Sprint 3 / WS-G — first-run setup wizard shown on /dashboard.
//
// Three short steps: company details → logo → first tender format. Each step
// hits a `/api/v1/me/*` endpoint and reloads.
'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'
import { ArrowRight, CheckCircle2 } from 'lucide-react'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dropzone } from '@/components/ui/dropzone'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface Props {
  initialDisplayName: string
  initialAddress: string
  initialGstin: string
  hasLogo: boolean
  hasFormat: boolean
}

type Step = 1 | 2 | 3 | 'done'

export function SetupWizard({
  initialDisplayName,
  initialAddress,
  initialGstin,
  hasLogo,
  hasFormat,
}: Props) {
  const router = useRouter()
  // Auto-skip steps the user has already completed previously.
  const computeStart = (): Step => {
    if (!initialDisplayName || !initialAddress) return 1
    if (!hasLogo) return 2
    if (!hasFormat) return 3
    return 'done'
  }

  const [step, setStep] = React.useState<Step>(computeStart)
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)

  const [displayName, setDisplayName] = React.useState(initialDisplayName)
  const [address, setAddress] = React.useState(initialAddress)
  const [gstin, setGstin] = React.useState(initialGstin)

  const advance = (next: Step) => {
    setError(null)
    setStep(next)
  }

  async function saveProfile() {
    if (!displayName.trim() || !address.trim()) {
      setError('Company name and address are required to continue.')
      return
    }
    setBusy(true)
    try {
      const resp = await fetch('/api/proxy/api/v1/me/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          display_name: displayName.trim(),
          address: address.trim(),
          gstin: gstin.trim() || undefined,
        }),
      })
      if (!resp.ok) throw new Error('Could not save your profile.')
      advance(2)
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function uploadLogo(files: File[]) {
    const file = files[0]
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const resp = await fetch('/api/proxy/api/v1/me/profile/logo', { method: 'POST', body: fd })
      if (!resp.ok) throw new Error('Logo upload failed.')
      advance(3)
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function uploadFormat(files: File[]) {
    const file = files[0]
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const name = file.name.replace(/\.[^.]+$/, '')
      const resp = await fetch(`/api/proxy/api/v1/me/sister-formats?name=${encodeURIComponent(name)}`, {
        method: 'POST',
        body: fd,
      })
      if (!resp.ok) throw new Error('Format upload failed.')
      advance('done')
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  if (step === 'done') return null

  const stepNumber = step === 1 ? 1 : step === 2 ? 2 : 3
  return (
    <Card className="mb-8 border-brand/30 bg-white">
      <CardHeader>
        <CardTitle>
          Welcome to DocSeva
          <span className="ml-2 inline-flex items-center text-sm font-medium text-ink-500">
            (Step {stepNumber} of 3 — about 60 seconds)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error ? <Alert tone="danger">{error}</Alert> : null}

        {step === 1 ? (
          <div className="grid gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="display_name">Company name</Label>
              <Input
                id="display_name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="ABC Enterprises"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="address">Address</Label>
              <Input
                id="address"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="12 MG Road, Bengaluru, KA — 560001"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="gstin">
                GSTIN <span className="text-xs text-ink-500">(optional)</span>
              </Label>
              <Input
                id="gstin"
                value={gstin}
                onChange={(e) => setGstin(e.target.value.toUpperCase())}
                placeholder="29ABCDE1234F1Z5"
              />
            </div>
            <div className="flex justify-between">
              <Button variant="ghost" onClick={() => advance(2)} disabled={busy}>
                Skip for now
              </Button>
              <Button onClick={saveProfile} disabled={busy}>
                Save & continue <ArrowRight className="h-4 w-4" aria-hidden />
              </Button>
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="space-y-4">
            <p className="text-sm text-ink-500">
              Upload your logo (PNG, JPG, or WEBP). It appears on every quote and invoice.
            </p>
            <Dropzone
              accept={['.png', '.jpg', '.jpeg', '.webp']}
              onFiles={uploadLogo}
              label="Drop your logo here"
              hint="Square logos look best. ≤ 15 MB."
              disabled={busy}
            />
            <div className="flex justify-between">
              <Button variant="ghost" onClick={() => advance(1)} disabled={busy}>
                ← Back
              </Button>
              <Button variant="outline" onClick={() => advance(3)} disabled={busy}>
                Skip logo
              </Button>
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="space-y-4">
            <p className="text-sm text-ink-500">
              Upload a sample of <em>your</em> tender format (PDF, DOC, or DOCX). DocSeva
              will use it as the template for every branded quote. You can add up to 10
              formats from Library.
            </p>
            <Dropzone
              accept={['.pdf', '.doc', '.docx']}
              onFiles={uploadFormat}
              label="Drop your tender format here"
              disabled={busy}
            />
            <div className="flex justify-between">
              <Button variant="ghost" onClick={() => advance(2)} disabled={busy}>
                ← Back
              </Button>
              <Button variant="outline" onClick={() => advance('done')} disabled={busy}>
                Skip & try a demo
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function SetupDone() {
  return (
    <Alert tone="success" className="mb-8" title="You're all set">
      <span className="inline-flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4" aria-hidden /> Drop a supplier quote on
        /new-quote to feel the magic.
      </span>
    </Alert>
  )
}

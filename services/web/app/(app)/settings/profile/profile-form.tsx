//genai: Sprint 4 / WS-I — Company profile form.
'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { CompanyProfileOut } from '@/lib/types'

type Field =
  | 'display_name'
  | 'address'
  | 'city'
  | 'state'
  | 'pincode'
  | 'gstin'
  | 'pan'
  | 'phone'
  | 'email'
  | 'website'

const FIELDS: { name: Field; label: string; placeholder?: string }[] = [
  { name: 'display_name', label: 'Company name', placeholder: 'ABC Enterprises' },
  { name: 'address', label: 'Address', placeholder: '12 MG Road' },
  { name: 'city', label: 'City', placeholder: 'Bengaluru' },
  { name: 'state', label: 'State', placeholder: 'Karnataka' },
  { name: 'pincode', label: 'Pincode', placeholder: '560001' },
  { name: 'gstin', label: 'GSTIN', placeholder: '29ABCDE1234F1Z5' },
  { name: 'pan', label: 'PAN', placeholder: 'ABCDE1234F' },
  { name: 'phone', label: 'Phone', placeholder: '+91 98xxxxxxxx' },
  { name: 'email', label: 'Public email', placeholder: 'sales@yourbiz.com' },
  { name: 'website', label: 'Website', placeholder: 'https://yourbiz.com' },
]

export function ProfileForm({ initial }: { initial: CompanyProfileOut | null }) {
  const router = useRouter()
  const [values, setValues] = React.useState<Record<Field, string>>(() => {
    const out = {} as Record<Field, string>
    for (const f of FIELDS) out[f.name] = (initial?.[f.name] as string | null) ?? ''
    return out
  })
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [success, setSuccess] = React.useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSuccess(null)
    try {
      const resp = await fetch('/api/proxy/api/v1/me/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(body.detail?.user_message || 'Could not save.')
      }
      setSuccess('Saved.')
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      {error ? <Alert tone="danger">{error}</Alert> : null}
      {success ? <Alert tone="success">{success}</Alert> : null}

      <div className="grid gap-4 sm:grid-cols-2">
        {FIELDS.map((f) => (
          <div key={f.name} className="space-y-1.5">
            <Label htmlFor={f.name}>{f.label}</Label>
            <Input
              id={f.name}
              placeholder={f.placeholder}
              value={values[f.name]}
              onChange={(e) =>
                setValues((prev) => ({ ...prev, [f.name]: e.target.value }))
              }
            />
          </div>
        ))}
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save changes'}
        </Button>
      </div>
    </form>
  )
}

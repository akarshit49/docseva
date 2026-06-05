//genai: Sprint 4 / WS-I — bank-details form.
'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'

import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { CompanyProfileOut } from '@/lib/types'

export function BankForm({ initial }: { initial: CompanyProfileOut | null }) {
  const router = useRouter()
  const [bankName, setBankName] = React.useState(initial?.bank_name ?? '')
  const [bankAccount, setBankAccount] = React.useState(initial?.bank_account ?? '')
  const [bankIfsc, setBankIfsc] = React.useState(initial?.bank_ifsc ?? '')
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
        body: JSON.stringify({
          bank_name: bankName,
          bank_account: bankAccount,
          bank_ifsc: bankIfsc.toUpperCase(),
        }),
      })
      if (!resp.ok) throw new Error('Could not save.')
      setSuccess('Saved.')
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      {error ? <Alert tone="danger">{error}</Alert> : null}
      {success ? <Alert tone="success">{success}</Alert> : null}

      <div className="space-y-1.5">
        <Label htmlFor="bank_name">Bank name</Label>
        <Input
          id="bank_name"
          value={bankName}
          onChange={(e) => setBankName(e.target.value)}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="bank_account">Account number</Label>
          <Input
            id="bank_account"
            value={bankAccount}
            onChange={(e) => setBankAccount(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="bank_ifsc">IFSC</Label>
          <Input
            id="bank_ifsc"
            value={bankIfsc}
            onChange={(e) => setBankIfsc(e.target.value.toUpperCase())}
            placeholder="HDFC0001234"
          />
        </div>
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save changes'}
        </Button>
      </div>
    </form>
  )
}

//genai: Sprint 3 / WS-F — /login page (email OTP).
//
// Two-step inline flow:
//   step 1: email → /api/auth/request-otp → reveal step 2
//   step 2: otp (+ optional name/company on first sign-in) → /api/auth/verify-otp
//
// On success the route handler set the cookie; we router-push to ?next or /dashboard.
'use client'

import * as React from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert } from '@/components/ui/alert'
import { Logo } from '@/components/shared/logo'

type Stage = 'email' | 'otp'

// `useSearchParams` causes Next.js to bail out of static prerendering unless
// it sits inside a Suspense boundary, so we split the read-the-?next-param
// body into a child component.
export default function LoginPage() {
  return (
    <React.Suspense fallback={null}>
      <LoginPageInner />
    </React.Suspense>
  )
}

function LoginPageInner() {
  const router = useRouter()
  const params = useSearchParams()
  const next = params.get('next') || '/dashboard'

  const [stage, setStage] = React.useState<Stage>('email')
  const [email, setEmail] = React.useState('')
  const [otp, setOtp] = React.useState('')
  const [name, setName] = React.useState('')
  const [companyName, setCompanyName] = React.useState('')
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [info, setInfo] = React.useState<string | null>(null)

  async function handleRequestOtp(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const resp = await fetch('/api/auth/request-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      if (!resp.ok && resp.status !== 204) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(body.user_message || 'Could not send code.')
      }
      setStage('otp')
      setInfo(`We sent a 6-digit code to ${email}. It expires in 10 minutes.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const resp = await fetch('/api/auth/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          otp,
          name: name || undefined,
          company_name: companyName || undefined,
        }),
      })
      const body = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        throw new Error(body.user_message || 'Invalid code.')
      }
      // Successful sign-in → router-push lands on the protected route.
      router.replace(next)
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-ink-100/40">
      <header className="border-b border-ink-100 bg-white">
        <div className="container flex h-16 items-center">
          <Link href="/">
            <Logo />
          </Link>
        </div>
      </header>
      <main className="container flex flex-1 items-center justify-center py-12">
        <div className="w-full max-w-md rounded-2xl border border-ink-100 bg-white p-8 shadow-card">
          <h1 className="text-2xl font-semibold text-ink-900">Sign in to DocSeva</h1>
          <p className="mt-1 text-sm text-ink-500">
            We'll email you a one-time code. No password to remember.
          </p>

          {error ? (
            <Alert tone="danger" className="mt-6">
              {error}
            </Alert>
          ) : null}
          {info && !error ? (
            <Alert tone="info" className="mt-6">
              {info}
            </Alert>
          ) : null}

          {stage === 'email' ? (
            <form className="mt-6 space-y-4" onSubmit={handleRequestOtp}>
              <div className="space-y-1.5">
                <Label htmlFor="email">Work email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  placeholder="you@yourbusiness.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <Button type="submit" block disabled={busy || !email.trim()}>
                {busy ? 'Sending…' : 'Send sign-in code'}
              </Button>
              <p className="text-center text-xs text-ink-500">
                New to DocSeva? Your account is created on first sign-in.
              </p>
            </form>
          ) : (
            <form className="mt-6 space-y-4" onSubmit={handleVerifyOtp}>
              <div className="space-y-1.5">
                <Label htmlFor="otp">6-digit code</Label>
                <Input
                  id="otp"
                  inputMode="numeric"
                  maxLength={6}
                  pattern="\d{6}"
                  required
                  placeholder="000000"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className="text-center text-2xl tracking-[0.5em]"
                />
              </div>
              <details className="rounded-lg border border-ink-100 px-3 py-2 text-xs text-ink-500 open:bg-ink-100/50">
                <summary className="cursor-pointer select-none">
                  First time? Add your name and company (optional)
                </summary>
                <div className="mt-3 space-y-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="name">Your name</Label>
                    <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="company">Business name</Label>
                    <Input
                      id="company"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                    />
                  </div>
                </div>
              </details>
              <Button type="submit" block disabled={busy || otp.length !== 6}>
                {busy ? 'Verifying…' : 'Verify & sign in'}
              </Button>
              <Button
                type="button"
                variant="ghost"
                block
                disabled={busy}
                onClick={() => {
                  setStage('email')
                  setOtp('')
                  setInfo(null)
                }}
              >
                ← Use a different email
              </Button>
            </form>
          )}
        </div>
      </main>
    </div>
  )
}

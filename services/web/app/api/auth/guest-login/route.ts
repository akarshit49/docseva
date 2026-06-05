//genai: Beta-testing guest login — bypasses email/OTP entirely.
//
// Generates (or reuses) a per-browser guest email, then signs that account in
// using the FastAPI TEST_OTP_CODE bypass. The result is a fully-authenticated
// session cookie identical to a normal OTP login — so the dashboard, quotas,
// and document storage all work per-user.
//
// Each browser keeps the same guest identity via a long-lived `docseva_guest_id`
// cookie so refreshing the page doesn't spin up a brand-new account.
//
// To disable this feature: remove TEST_OTP_CODE from the API .env.
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'

import { authRequestOtp, authVerifyOtp } from '@/lib/api'
import { writeSession } from '@/lib/session'

const GUEST_COOKIE = 'docseva_guest_id'
const GUEST_DOMAIN = 'guest.docseva.local'
const BYPASS_OTP_CODE = process.env.TEST_OTP_CODE || 'docseva'

function randomGuestId(): string {
  return (
    'g-' +
    Math.random().toString(36).slice(2, 10) +
    Date.now().toString(36)
  )
}

function resolveOrigin(req: Request): string {
  // Behind Nginx the public host arrives in X-Forwarded-Host / Host headers.
  const xfHost = req.headers.get('x-forwarded-host')
  const host = req.headers.get('host')
  const proto = req.headers.get('x-forwarded-proto') || 'http'
  const publicHost = xfHost || host
  if (publicHost) return `${proto}://${publicHost}`
  return new URL(req.url).origin
}

async function loginAsGuest(req: Request): Promise<NextResponse> {
  const jar = await cookies()
  let guestId = jar.get(GUEST_COOKIE)?.value
  if (!guestId) {
    guestId = randomGuestId()
  }
  const email = `${guestId}@${GUEST_DOMAIN}`
  const origin = resolveOrigin(req)

  try {
    await authRequestOtp(email)
    const auth = await authVerifyOtp({ email, otp: BYPASS_OTP_CODE })
    writeSession({
      accessToken: auth.tokens.access_token,
      refreshToken: auth.tokens.refresh_token,
      accessExpiresAt:
        Math.floor(Date.now() / 1000) + (auth.tokens.expires_in ?? 3600),
    })
    const res = NextResponse.redirect(new URL('/dashboard', origin))
    res.cookies.set(GUEST_COOKIE, guestId, {
      httpOnly: false,
      sameSite: 'lax',
      path: '/',
      maxAge: 60 * 60 * 24 * 90,
    })
    return res
  } catch {
    return NextResponse.redirect(new URL('/?guest_failed=1', origin))
  }
}

export async function GET(req: Request) {
  return loginAsGuest(req)
}

export async function POST(req: Request) {
  return loginAsGuest(req)
}

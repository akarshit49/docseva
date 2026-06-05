//genai: Sprint 3 / WS-F — clear the session cookie + revoke the refresh on the API.
import { NextResponse } from 'next/server'

import { ApiError, authLogout } from '@/lib/api'
import { clearSession, readSession } from '@/lib/session'

export async function POST() {
  const session = readSession()
  if (session) {
    try {
      await authLogout(session.refreshToken)
    } catch (err) {
      // Logout best-effort: if the API is unreachable we still clear the cookie.
      if (!(err instanceof ApiError)) {
        // swallow
      }
    }
  }
  clearSession()
  return NextResponse.json({ ok: true })
}

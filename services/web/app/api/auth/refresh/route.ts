//genai: Sprint 3 / WS-F — explicit refresh endpoint. The server-side fetch
//        wrapper already handles transparent refresh on 401; this is exposed
//        so the client can trigger a refresh proactively (e.g. when a long-
//        lived tab wakes up after sleep).
import { NextResponse } from 'next/server'

import { env } from '@/lib/env'
import { readSession, writeSession } from '@/lib/session'
import type { WebTokens } from '@/lib/types'

export async function POST() {
  const session = readSession()
  if (!session?.refreshToken) {
    return NextResponse.json({ user_message: 'Not signed in.' }, { status: 401 })
  }
  const resp = await fetch(`${env.apiInternalUrl}/api/v1/auth/web/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: session.refreshToken }),
    cache: 'no-store',
  })
  if (!resp.ok) {
    return NextResponse.json({ user_message: 'Refresh failed.' }, { status: resp.status })
  }
  const tokens = (await resp.json()) as WebTokens
  writeSession({
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    accessExpiresAt: Math.floor(Date.now() / 1000) + tokens.expires_in,
  })
  return NextResponse.json({ ok: true })
}

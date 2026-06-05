//genai: Sprint 3 / WS-F — server-side session cookie helpers.
//
// The session cookie holds the FastAPI tokens. It is httpOnly + SameSite=Lax
// (+ Secure in production), so the access token never reaches client JS — a
// stolen XSS payload can't read it.
//
// Cookie value shape (JSON): { a: <accessToken>, r: <refreshToken>, e: <accessExpiresAt> }
import { cookies } from 'next/headers'

import { env } from './env'

export interface SessionPayload {
  accessToken: string
  refreshToken: string
  /** Unix-seconds when the access token expires (best-effort). */
  accessExpiresAt: number
}

interface RawCookie {
  a: string
  r: string
  e: number
}

const COOKIE_OPTIONS = {
  httpOnly: true,
  sameSite: 'lax' as const,
  path: '/',
  secure: env.secureCookie,
  maxAge: env.cookieMaxAgeSeconds,
}

export function readSession(): SessionPayload | null {
  const raw = cookies().get(env.cookieName)?.value
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as RawCookie
    if (!parsed.a || !parsed.r) return null
    return {
      accessToken: parsed.a,
      refreshToken: parsed.r,
      accessExpiresAt: parsed.e ?? 0,
    }
  } catch {
    return null
  }
}

export function writeSession(payload: SessionPayload): void {
  const raw: RawCookie = {
    a: payload.accessToken,
    r: payload.refreshToken,
    e: payload.accessExpiresAt,
  }
  cookies().set(env.cookieName, JSON.stringify(raw), COOKIE_OPTIONS)
}

export function clearSession(): void {
  cookies().delete(env.cookieName)
}

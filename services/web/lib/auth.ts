//genai: Sprint 3 / WS-F — server-side auth guards used by protected pages.
import 'server-only'

import { redirect } from 'next/navigation'

import { fetchMe } from './api'
import type { MeResponse } from './types'

/**
 * Use from any server component / page in the (app) group. Redirects to /login
 * if the visitor isn't authenticated, otherwise returns the canonical user/org
 * payload. Cached per-request so multiple components sharing a render don't
 * each round-trip to FastAPI.
 */
export async function requireMe(): Promise<MeResponse> {
  const me = await fetchMe()
  if (!me) redirect('/login')
  return me
}

/**
 * Soft variant for landing/login pages: returns null when not logged in.
 */
export async function optionalMe(): Promise<MeResponse | null> {
  return fetchMe()
}

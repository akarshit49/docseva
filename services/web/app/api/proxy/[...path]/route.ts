//genai: Authenticated catch-all proxy route.
//
// Problem: client-side components can't read the httpOnly session cookie, so
// they can't attach `Authorization: Bearer` when calling FastAPI directly.
//
// Solution: all mutation fetches are directed here (e.g. `/api/proxy/api/v1/me/profile`).
// This handler runs on the Next.js server, reads the cookie, and forwards the
// request to FastAPI with the correct Authorization header.
//
// Path rewrite: `/api/proxy/api/v1/foo` → `<API_INTERNAL_URL>/api/v1/foo`
import { NextResponse } from 'next/server'

import { env } from '@/lib/env'
import { readSession } from '@/lib/session'

type RouteContext = { params: { path: string[] } }

async function handler(req: Request, { params }: RouteContext): Promise<Response> {
  const session = readSession()
  if (!session) {
    return NextResponse.json(
      { code: 'E401', user_message: 'Not authenticated.' },
      { status: 401 },
    )
  }

  // Rebuild the upstream path from the catch-all segments.
  // Incoming: /api/proxy/api/v1/me/profile  →  params.path = ['api','v1','me','profile']
  const upstreamPath = '/' + params.path.join('/')

  // Forward any query-string from the original request URL.
  const incoming = new URL(req.url)
  const upstreamUrl = `${env.apiInternalUrl}${upstreamPath}${incoming.search}`

  // Copy incoming headers and inject Authorization; drop Next.js internal headers.
  const headers = new Headers(req.headers)
  headers.set('Authorization', `Bearer ${session.accessToken}`)
  headers.delete('host') // let fetch set the correct Host for the upstream

  // For non-GET/HEAD requests, pass the body through unchanged.
  const hasBody = !['GET', 'HEAD'].includes(req.method.toUpperCase())
  const body = hasBody ? req.body : undefined

  const upstream = await fetch(upstreamUrl, {
    method: req.method,
    headers,
    body,
    // @ts-expect-error -- Node.js fetch needs this to stream request bodies
    duplex: 'half',
  })

  // Stream the response back as-is, preserving status + headers.
  const responseHeaders = new Headers(upstream.headers)
  // Remove transfer-encoding so Next.js can re-encode if needed.
  responseHeaders.delete('transfer-encoding')

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  })
}

export const GET = handler
export const POST = handler
export const PUT = handler
export const PATCH = handler
export const DELETE = handler

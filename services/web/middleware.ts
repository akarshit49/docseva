//genai: Sprint 3 / WS-F — protect authenticated routes at the edge.
//
// Pages under (app)/* require a session cookie. We can't fully validate the
// JWT here (it would require importing jose into the edge runtime + the
// secret), so middleware just checks "cookie present and parseable". Pages
// themselves call `requireMe()` which is a fresh, authoritative check.
import { type NextRequest, NextResponse } from 'next/server'

const PROTECTED_PREFIXES = [
  '/dashboard',
  '/new-quote',
  '/library',
  '/tools',
  '/settings',
  '/billing',
]

function isProtected(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`))
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl
  if (!isProtected(pathname)) return NextResponse.next()

  const cookieName = process.env.WEB_SESSION_COOKIE || 'docseva_session'
  const raw = req.cookies.get(cookieName)?.value
  let ok = false
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as { a?: string; r?: string }
      ok = Boolean(parsed.a && parsed.r)
    } catch {
      ok = false
    }
  }
  if (!ok) {
    const url = req.nextUrl.clone()
    url.pathname = '/login'
    url.searchParams.set('next', pathname)
    return NextResponse.redirect(url)
  }
  return NextResponse.next()
}

export const config = {
  matcher: [
    '/dashboard/:path*',
    '/new-quote/:path*',
    '/library/:path*',
    '/tools/:path*',
    '/settings/:path*',
    '/billing/:path*',
  ],
}

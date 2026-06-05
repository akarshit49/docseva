//genai: Sprint 3 / WS-F — typed access to environment variables.
//        Centralising this means every file reads the same names and we get
//        a single place to fail loudly when a required var is missing.

export const env = {
  // The FastAPI URL the Next server uses for proxied + auth route handlers.
  apiInternalUrl:
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_INTERNAL_URL ||
    'http://localhost:8000',
  // The URL the browser uses when it needs to fetch media directly.
  publicApiUrl: process.env.NEXT_PUBLIC_API_BASE_URL || '',
  cookieName: process.env.WEB_SESSION_COOKIE || 'docseva_session',
  // 7 days — refresh tokens last 30d in the API; we keep our cookie shorter
  // so a stolen cookie has a tighter blast radius.
  cookieMaxAgeSeconds: 60 * 60 * 24 * 7,
  isProduction: process.env.NODE_ENV === 'production',
  // Set COOKIE_SECURE=false in .env when running behind HTTP (no TLS).
  // Defaults to true in production so Safari doesn't drop the session cookie.
  secureCookie: process.env.COOKIE_SECURE !== 'false',
} as const

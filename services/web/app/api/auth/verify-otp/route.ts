//genai: Sprint 3 / WS-F — proxy POST /api/auth/verify-otp → FastAPI.
//
// On success we write the tokens to an httpOnly cookie. The client only sees
// `{ ok: true, is_new }`; the bearer token never reaches the browser.
import { NextResponse } from 'next/server'

import { authVerifyOtp, ApiError } from '@/lib/api'
import { verifyOtpSchema } from '@/lib/schemas'
import { writeSession } from '@/lib/session'

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}))
  const parsed = verifyOtpSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { code: 'E007', user_message: parsed.error.errors[0]?.message ?? 'Bad input.' },
      { status: 400 },
    )
  }
  try {
    const auth = await authVerifyOtp(parsed.data)
    writeSession({
      accessToken: auth.tokens.access_token,
      refreshToken: auth.tokens.refresh_token,
      accessExpiresAt:
        Math.floor(Date.now() / 1000) + (auth.tokens.expires_in ?? 3600),
    })
    return NextResponse.json({
      ok: true,
      is_new: auth.is_new,
      user_id: auth.user.id,
      organization_id: auth.organization.id,
    })
  } catch (err) {
    if (err instanceof ApiError) {
      return NextResponse.json(err.payload ?? { user_message: err.message }, {
        status: err.status,
      })
    }
    return NextResponse.json(
      { code: 'E005', user_message: 'Could not reach the auth service.' },
      { status: 503 },
    )
  }
}

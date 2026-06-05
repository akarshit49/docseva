//genai: Sprint 3 / WS-F — proxy POST /api/auth/request-otp → FastAPI.
import { NextResponse } from 'next/server'

import { authRequestOtp, ApiError } from '@/lib/api'
import { loginRequestSchema } from '@/lib/schemas'

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}))
  const parsed = loginRequestSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { code: 'E007', user_message: parsed.error.errors[0]?.message ?? 'Bad input.' },
      { status: 400 },
    )
  }
  try {
    await authRequestOtp(parsed.data.email)
    // Always 204 even if the email is unknown — no enumeration.
    return new NextResponse(null, { status: 204 })
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

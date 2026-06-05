//genai: Sprint 3 / WS-F — server-side typed fetch wrapper for the FastAPI service.
//
// Use this from server components, route handlers, and server actions. Never
// import this from client components — the access token must stay on the
// server. Client components call /api/auth/* (which we own) or use rewrites
// for proxied calls.
import 'server-only'

import { env } from './env'
import { readSession, writeSession } from './session'
import type {
  ApiErrorPayload,
  ChannelLinkOut,
  ChannelLinkStartResponse,
  CompanyProfileOut,
  DocumentMetadataOut,
  DocumentOut,
  MeResponse,
  ProcessResponse,
  SisterFormatOut,
  WebAuthResponse,
  WebTokens,
} from './types'

export class ApiError extends Error {
  status: number
  payload?: ApiErrorPayload
  retryable: boolean
  code?: string

  constructor(message: string, opts: {
    status: number
    payload?: ApiErrorPayload
    retryable?: boolean
    code?: string
  }) {
    super(message)
    this.status = opts.status
    this.payload = opts.payload
    this.retryable = opts.retryable ?? false
    this.code = opts.code
  }
}

interface CallOptions {
  method?: string
  body?: unknown
  formData?: FormData
  headers?: Record<string, string>
  // When true, attach the bearer token from the session cookie.
  withAuth?: boolean
  // When true and a 401 happens, try refresh-then-retry once.
  refreshOnUnauthorized?: boolean
  cache?: RequestCache
  signal?: AbortSignal
}

async function callApi<T>(path: string, opts: CallOptions = {}): Promise<T> {
  const {
    method = 'GET',
    body,
    formData,
    headers = {},
    withAuth = true,
    refreshOnUnauthorized = true,
    cache = 'no-store',
    signal,
  } = opts

  const finalHeaders: Record<string, string> = { ...headers }
  if (!formData && body !== undefined && finalHeaders['Content-Type'] === undefined) {
    finalHeaders['Content-Type'] = 'application/json'
  }

  if (withAuth) {
    const session = readSession()
    if (session) {
      finalHeaders.Authorization = `Bearer ${session.accessToken}`
    }
  }

  const url = `${env.apiInternalUrl}${path}`
  const init: RequestInit = {
    method,
    headers: finalHeaders,
    cache,
    signal,
  }
  if (formData) {
    init.body = formData
  } else if (body !== undefined) {
    init.body = typeof body === 'string' ? body : JSON.stringify(body)
  }

  let resp = await fetch(url, init)

  if (resp.status === 401 && withAuth && refreshOnUnauthorized) {
    const refreshed = await refreshTokens()
    if (refreshed) {
      finalHeaders.Authorization = `Bearer ${refreshed.access_token}`
      resp = await fetch(url, {
        ...init,
        headers: finalHeaders,
      })
    }
  }

  if (resp.status === 204) return undefined as T

  const text = await resp.text()
  const json: unknown = text ? safeParse(text) : null

  if (!resp.ok) {
    const payload = extractApiError(json)
    throw new ApiError(payload?.user_message || resp.statusText, {
      status: resp.status,
      payload: payload ?? undefined,
      code: payload?.code,
      retryable: payload?.retryable ?? resp.status >= 500,
    })
  }
  return json as T
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function extractApiError(body: unknown): ApiErrorPayload | null {
  if (!body || typeof body !== 'object') return null
  const obj = body as Record<string, unknown>
  // FastAPI default error shape: { detail: ApiError | string }
  const detail = obj.detail
  if (detail && typeof detail === 'object' && (detail as Record<string, unknown>).code) {
    return detail as unknown as ApiErrorPayload
  }
  if (typeof detail === 'string') {
    return { code: 'E009', user_message: detail, retryable: false }
  }
  if (typeof obj.code === 'string' && typeof obj.user_message === 'string') {
    return obj as unknown as ApiErrorPayload
  }
  return null
}

async function refreshTokens(): Promise<WebTokens | null> {
  const session = readSession()
  if (!session?.refreshToken) return null
  try {
    const resp = await fetch(`${env.apiInternalUrl}/api/v1/auth/web/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: session.refreshToken }),
      cache: 'no-store',
    })
    if (!resp.ok) return null
    const tokens = (await resp.json()) as WebTokens
    writeSession({
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      accessExpiresAt: Math.floor(Date.now() / 1000) + tokens.expires_in,
    })
    return tokens
  } catch {
    return null
  }
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function authRequestOtp(email: string): Promise<void> {
  await callApi('/api/v1/auth/web/request-otp', {
    method: 'POST',
    body: { email },
    withAuth: false,
  })
}

export async function authVerifyOtp(input: {
  email: string
  otp: string
  name?: string
  company_name?: string
}): Promise<WebAuthResponse> {
  return callApi('/api/v1/auth/web/verify-otp', {
    method: 'POST',
    body: input,
    withAuth: false,
  })
}

export async function authLogout(refreshToken: string): Promise<void> {
  await callApi('/api/v1/auth/web/logout', {
    method: 'POST',
    body: { refresh_token: refreshToken },
  })
}

// ── /me + profile ─────────────────────────────────────────────────────────────

export async function fetchMe(): Promise<MeResponse | null> {
  try {
    return await callApi<MeResponse>('/api/v1/auth/me')
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null
    throw err
  }
}

export async function updateMyProfile(
  body: Partial<CompanyProfileOut>,
): Promise<CompanyProfileOut> {
  return callApi<CompanyProfileOut>('/api/v1/me/profile', {
    method: 'PUT',
    body,
  })
}

export async function uploadMyLogo(file: File): Promise<CompanyProfileOut> {
  const fd = new FormData()
  fd.append('file', file)
  return callApi<CompanyProfileOut>('/api/v1/me/profile/logo', {
    method: 'POST',
    formData: fd,
  })
}

// ── Sister formats ───────────────────────────────────────────────────────────

export async function listSisterFormats(): Promise<SisterFormatOut[]> {
  return callApi<SisterFormatOut[]>('/api/v1/me/sister-formats')
}

export async function uploadSisterFormat(
  name: string,
  file: File,
): Promise<SisterFormatOut> {
  const fd = new FormData()
  fd.append('file', file)
  const qs = new URLSearchParams({ name }).toString()
  return callApi<SisterFormatOut>(`/api/v1/me/sister-formats?${qs}`, {
    method: 'POST',
    formData: fd,
  })
}

export async function deleteSisterFormat(id: string): Promise<void> {
  await callApi(`/api/v1/me/sister-formats/${id}`, { method: 'DELETE' })
}

// ── Documents (history) ──────────────────────────────────────────────────────

export async function listMyDocuments(
  params: {
    limit?: number
    feature?: string
    document_type?: string
  } = {},
): Promise<DocumentOut[]> {
  const qs = new URLSearchParams()
  if (params.limit) qs.set('limit', String(params.limit))
  if (params.feature) qs.set('feature', params.feature)
  if (params.document_type) qs.set('document_type', params.document_type)
  const q = qs.toString()
  return callApi<DocumentOut[]>(`/api/v1/me/documents${q ? `?${q}` : ''}`)
}

export async function getDocumentMetadata(id: string): Promise<DocumentMetadataOut> {
  return callApi<DocumentMetadataOut>(`/api/v1/me/documents/${id}/metadata`)
}

// ── Channels ─────────────────────────────────────────────────────────────────

export async function listChannels(): Promise<ChannelLinkOut[]> {
  return callApi<ChannelLinkOut[]>('/api/v1/channels')
}

export async function startChannelLink(
  channel: 'telegram' | 'whatsapp',
): Promise<ChannelLinkStartResponse> {
  return callApi<ChannelLinkStartResponse>('/api/v1/channels/web/start-link', {
    method: 'POST',
    body: { channel },
  })
}

export async function deleteChannelLink(id: string): Promise<void> {
  await callApi(`/api/v1/channels/${id}`, { method: 'DELETE' })
}

// ── DPDP (Sprint 6) ──────────────────────────────────────────────────────────

export interface AccountExportResponse {
  exported_at: string
  exporter_version: number
  user: Record<string, unknown>
  organization: Record<string, unknown>
  company_profile: Record<string, unknown> | null
  channel_links: unknown[]
  documents: unknown[]
  sister_formats: unknown[]
  notice: string
}

export interface AccountDeleteResponse {
  status: string
  user_id: string
  organization_id: string
  deletion_requested_at: string
  grace_period_days: number
  message: string
}

export async function exportMyAccount(): Promise<AccountExportResponse> {
  return callApi<AccountExportResponse>('/api/v1/me/account/export')
}

export async function deleteMyAccount(): Promise<AccountDeleteResponse> {
  return callApi<AccountDeleteResponse>('/api/v1/me/account/delete', {
    method: 'POST',
  })
}

// ── /process/<feature> ───────────────────────────────────────────────────────

export interface ProcessInput {
  feature: string
  file?: File
  files?: File[]
  params?: Record<string, unknown>
  format_id?: string
  mode?: 'preview' | 'final'
}

export async function processFeature(input: ProcessInput): Promise<ProcessResponse> {
  const fd = new FormData()
  fd.append('mode', input.mode ?? 'final')
  if (input.params) fd.append('params', JSON.stringify(input.params))
  if (input.format_id) fd.append('format_id', input.format_id)
  if (input.file) fd.append('file', input.file)
  if (input.files) {
    for (const f of input.files) fd.append('files', f)
  }
  return callApi<ProcessResponse>(`/api/v1/process/${input.feature}`, {
    method: 'POST',
    formData: fd,
  })
}

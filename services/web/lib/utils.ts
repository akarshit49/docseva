//genai: Sprint 3 / WS-F — shared utility helpers.
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Tailwind-aware class combiner used by every shadcn-style primitive. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Format a paise-free rupee value with Indian digit grouping. */
export function formatRupees(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const num = typeof value === 'string' ? Number(value) : value
  if (Number.isNaN(num)) return '—'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(num)
}

/** Quick byte → MB helper for size pills. */
export function bytesToMb(bytes: number): string {
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

/** ISO timestamp → "31 May 2026". */
export function humanDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso.slice(0, 10)
  return date.toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

/** Hide an email/PII string for non-sensitive logs (`a***@example.com`). */
export function maskEmail(email: string): string {
  const [user, domain] = email.split('@')
  if (!user || !domain) return email
  const head = user.slice(0, 1)
  return `${head}${'*'.repeat(Math.max(1, user.length - 1))}@${domain}`
}

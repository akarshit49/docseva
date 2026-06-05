//genai: Sprint 6 follow-up — pure-function tests for lib/utils.
import { describe, expect, it } from 'vitest'

import { bytesToMb, cn, formatRupees, humanDate, maskEmail } from '@/lib/utils'

describe('cn (tailwind merger)', () => {
  it('joins truthy values and resolves tailwind conflicts', () => {
    // `tw-merge` collapses conflicting "px-*" classes — proves we're using it.
    expect(cn('px-2', 'px-4')).toBe('px-4')
    expect(cn('p-2', undefined, false && 'hidden', 'text-sm')).toBe('p-2 text-sm')
  })
})

describe('formatRupees', () => {
  it('formats whole-rupee values with Indian grouping', () => {
    // ₹ glyph + Indian-style grouping ("1,23,456"). Different OSes render the
    // separator as either ASCII space, narrow no-break space, or non-breaking
    // space — we assert on shape rather than exact whitespace.
    const out = formatRupees(123456)
    expect(out).toMatch(/₹/)
    expect(out.replace(/\s/g, '')).toContain('1,23,456')
  })

  it('handles strings and falsey inputs gracefully', () => {
    expect(formatRupees('0')).toMatch(/₹/)
    expect(formatRupees(null)).toBe('—')
    expect(formatRupees(undefined)).toBe('—')
    expect(formatRupees('')).toBe('—')
    expect(formatRupees('not a number')).toBe('—')
  })
})

describe('bytesToMb', () => {
  it('returns a one-decimal MB string', () => {
    expect(bytesToMb(1_048_576)).toBe('1.0 MB')
    expect(bytesToMb(5 * 1_048_576)).toBe('5.0 MB')
    expect(bytesToMb(0)).toBe('0.0 MB')
  })
})

describe('humanDate', () => {
  it('renders a localised "31 May 2026" form', () => {
    const result = humanDate('2026-05-31T10:00:00Z')
    // Different ICU versions abbreviate months slightly differently ("May" vs
    // "May"). We just assert the year + day are present.
    expect(result).toContain('2026')
    expect(result).toMatch(/3[01]/)
  })

  it('returns empty string on missing input', () => {
    expect(humanDate(null)).toBe('')
    expect(humanDate(undefined)).toBe('')
  })

  it('falls back to the first 10 chars of the input on invalid dates', () => {
    // `humanDate` returns `iso.slice(0, 10)` for unparseable strings. We feed
    // a clearly invalid value and assert the truncation.
    expect(humanDate('this-is-not-a-real-date')).toBe('this-is-no')
  })
})

describe('maskEmail', () => {
  it('masks everything after the first character of the local part', () => {
    // 8-char local part → 1 visible char + 7 asterisks.
    expect(maskEmail('akarshit@docseva.in')).toBe('a*******@docseva.in')
    // Single-char local part still gets at least one mask (`Math.max(1, …)`).
    expect(maskEmail('x@y.com')).toBe('x*@y.com')
  })

  it('returns the input unchanged for malformed emails', () => {
    expect(maskEmail('no-at-sign')).toBe('no-at-sign')
  })
})

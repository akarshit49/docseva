//genai: Sprint 6 follow-up — Zod schema tests.
//
// These mirror the API's Pydantic shapes (single source of truth comment in
// schemas.ts). A regression here would mean the form validation drifts from
// what the API accepts, so we lock the rules down explicitly.
import { describe, expect, it } from 'vitest'

import {
  bankSchema,
  companyProfileSchema,
  emailSchema,
  loginRequestSchema,
  numberingSchema,
  otpSchema,
  verifyOtpSchema,
} from '@/lib/schemas'

describe('emailSchema', () => {
  it.each([
    ['ak@docseva.in', true],
    ['user.name+tag@example.co.in', true],
    ['no-at-sign', false],
    ['a@', false],
    ['', false],
  ])('validates %s ⇒ %s', (input, ok) => {
    expect(emailSchema.safeParse(input).success).toBe(ok)
  })
})

describe('otpSchema', () => {
  it.each([
    ['123456', true],
    ['000000', true],
    ['12345', false],   // too short
    ['1234567', false], // too long
    ['12a456', false],  // non-digit
  ])('validates %s ⇒ %s', (input, ok) => {
    expect(otpSchema.safeParse(input).success).toBe(ok)
  })
})

describe('loginRequestSchema / verifyOtpSchema', () => {
  it('login requires only a valid email', () => {
    expect(loginRequestSchema.safeParse({ email: 'a@b.co' }).success).toBe(true)
    expect(loginRequestSchema.safeParse({ email: 'bad' }).success).toBe(false)
  })

  it('verify requires email + 6-digit OTP, name/company optional', () => {
    expect(
      verifyOtpSchema.safeParse({ email: 'a@b.co', otp: '123456' }).success,
    ).toBe(true)
    expect(
      verifyOtpSchema.safeParse({
        email: 'a@b.co',
        otp: '123456',
        name: 'Ak',
        company_name: 'Acme',
      }).success,
    ).toBe(true)
    expect(
      verifyOtpSchema.safeParse({ email: 'a@b.co', otp: '12' }).success,
    ).toBe(false)
  })
})

describe('companyProfileSchema', () => {
  it('requires a display_name', () => {
    const res = companyProfileSchema.safeParse({})
    expect(res.success).toBe(false)
  })

  it('accepts a minimal profile', () => {
    const res = companyProfileSchema.safeParse({ display_name: 'Acme' })
    expect(res.success).toBe(true)
  })

  it('enforces 6-digit pincode when provided', () => {
    const ok = companyProfileSchema.safeParse({
      display_name: 'Acme',
      pincode: '560001',
    })
    expect(ok.success).toBe(true)

    const bad = companyProfileSchema.safeParse({
      display_name: 'Acme',
      pincode: '12345',
    })
    expect(bad.success).toBe(false)
  })

  it('enforces 15-char alphanumeric GSTIN when provided', () => {
    const ok = companyProfileSchema.safeParse({
      display_name: 'Acme',
      gstin: '29ABCDE1234F1Z5',
    })
    expect(ok.success).toBe(true)

    const bad = companyProfileSchema.safeParse({
      display_name: 'Acme',
      gstin: 'too-short',
    })
    expect(bad.success).toBe(false)
  })

  it('allows empty strings for optional fields (HTML form default)', () => {
    const ok = companyProfileSchema.safeParse({
      display_name: 'Acme',
      pincode: '',
      gstin: '',
      pan: '',
    })
    expect(ok.success).toBe(true)
  })
})

describe('bankSchema', () => {
  it('requires a well-formed IFSC', () => {
    expect(
      bankSchema.safeParse({
        bank_name: 'HDFC',
        bank_account: '1234567890',
        bank_ifsc: 'HDFC0000123',
      }).success,
    ).toBe(true)
    expect(
      bankSchema.safeParse({
        bank_name: 'HDFC',
        bank_account: '12',
        bank_ifsc: 'BAD',
      }).success,
    ).toBe(false)
  })
})

describe('numberingSchema', () => {
  it('enforces 1–8 char prefixes', () => {
    expect(
      numberingSchema.safeParse({
        invoice_prefix: 'INV',
        po_prefix: 'PO',
        quotation_prefix: 'Q',
      }).success,
    ).toBe(true)
    expect(
      numberingSchema.safeParse({
        invoice_prefix: '',
        po_prefix: 'PO',
        quotation_prefix: 'Q',
      }).success,
    ).toBe(false)
    expect(
      numberingSchema.safeParse({
        invoice_prefix: 'TOOLONGPREFIX',
        po_prefix: 'PO',
        quotation_prefix: 'Q',
      }).success,
    ).toBe(false)
  })
})

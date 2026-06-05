//genai: Sprint 3 / WS-F — Zod schemas mirroring Pydantic shapes on the API.
//        Single source of truth used by react-hook-form + our typed fetch client.
import { z } from 'zod'

export const emailSchema = z
  .string()
  .min(3, 'Enter a valid email.')
  .email('Enter a valid email.')

export const otpSchema = z
  .string()
  .regex(/^\d{6}$/, 'Enter the 6-digit code.')

export const loginRequestSchema = z.object({ email: emailSchema })
export const verifyOtpSchema = z.object({
  email: emailSchema,
  otp: otpSchema,
  name: z.string().optional(),
  company_name: z.string().optional(),
})

export const companyProfileSchema = z.object({
  display_name: z.string().min(2, 'Company name is required.'),
  address: z.string().optional().or(z.literal('')),
  city: z.string().optional().or(z.literal('')),
  state: z.string().optional().or(z.literal('')),
  pincode: z
    .string()
    .regex(/^\d{6}$/, 'Pincode must be 6 digits.')
    .optional()
    .or(z.literal('')),
  gstin: z
    .string()
    .regex(/^[0-9A-Z]{15}$/i, 'GSTIN must be 15 alphanumeric characters.')
    .optional()
    .or(z.literal('')),
  pan: z
    .string()
    .regex(/^[A-Z]{5}[0-9]{4}[A-Z]$/i, 'PAN format looks wrong.')
    .optional()
    .or(z.literal('')),
  phone: z.string().optional().or(z.literal('')),
  email: z.string().optional().or(z.literal('')),
  website: z.string().optional().or(z.literal('')),
})

export const bankSchema = z.object({
  bank_name: z.string().min(2),
  bank_account: z.string().min(4),
  bank_ifsc: z.string().regex(/^[A-Z]{4}0[A-Z0-9]{6}$/i, 'IFSC format looks wrong.'),
})

export const numberingSchema = z.object({
  invoice_prefix: z.string().min(1).max(8),
  po_prefix: z.string().min(1).max(8),
  quotation_prefix: z.string().min(1).max(8),
})

export type CompanyProfileForm = z.infer<typeof companyProfileSchema>
export type BankForm = z.infer<typeof bankSchema>
export type NumberingForm = z.infer<typeof numberingSchema>

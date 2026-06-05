//genai: Sprint 3 / WS-H — Zustand store for the anchor flow wizard.
//
// Holds:
//   - the staged file (kept as a File reference)
//   - the parsed preview data (from /process/sister_quote?mode=preview)
//   - the chosen format id + output ext
//   - the price-adjust selection
//   - the final ProcessResponse (so step 4 has the download URL)
//
// State is intentionally kept in memory only — refreshing the page resets the
// wizard. Persisting drafts is a Sprint 4 follow-up (uses /api/v1/drafts).
'use client'

import { create } from 'zustand'

import type { ProcessResponse, QuotePreview } from '../types'

export type WizardStep = 1 | 2 | 3 | 4

interface NewQuoteState {
  step: WizardStep
  file: File | null
  preview: QuotePreview | null
  parsedRaw: Record<string, unknown> | null
  formatId: string | null
  outputExt: 'docx' | 'pdf'
  priceAdjustPct: number
  result: ProcessResponse | null
  errorMessage: string | null
  isWorking: boolean

  setStep: (step: WizardStep) => void
  setFile: (file: File | null) => void
  setPreview: (preview: QuotePreview | null, raw: Record<string, unknown> | null) => void
  setFormat: (formatId: string | null) => void
  setOutputExt: (ext: 'docx' | 'pdf') => void
  setPriceAdjustPct: (pct: number) => void
  setResult: (result: ProcessResponse | null) => void
  setWorking: (working: boolean) => void
  setError: (message: string | null) => void
  reset: () => void
}

export const useNewQuoteStore = create<NewQuoteState>((set) => ({
  step: 1,
  file: null,
  preview: null,
  parsedRaw: null,
  formatId: null,
  outputExt: 'docx',
  priceAdjustPct: 0,
  result: null,
  errorMessage: null,
  isWorking: false,

  setStep: (step) => set({ step }),
  setFile: (file) => set({ file }),
  setPreview: (preview, parsedRaw) => set({ preview, parsedRaw }),
  setFormat: (formatId) => set({ formatId }),
  setOutputExt: (outputExt) => set({ outputExt }),
  setPriceAdjustPct: (priceAdjustPct) => set({ priceAdjustPct }),
  setResult: (result) => set({ result }),
  setWorking: (isWorking) => set({ isWorking }),
  setError: (errorMessage) => set({ errorMessage }),
  reset: () =>
    set({
      step: 1,
      file: null,
      preview: null,
      parsedRaw: null,
      formatId: null,
      outputExt: 'docx',
      priceAdjustPct: 0,
      result: null,
      errorMessage: null,
      isWorking: false,
    }),
}))

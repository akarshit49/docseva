//genai: Sprint 6 follow-up — Zustand store transitions for the anchor wizard.
//
// The store is the source of truth for the multi-step flow. If a setter ever
// stops updating its slice, the wizard breaks silently — this lock-down test
// catches that.
import { beforeEach, describe, expect, it } from 'vitest'

import { useNewQuoteStore } from '@/lib/store/new-quote-store'

const initial = () => useNewQuoteStore.getState()

beforeEach(() => {
  // Reset between tests so each starts from a clean slice.
  useNewQuoteStore.getState().reset()
})

describe('useNewQuoteStore', () => {
  it('starts on step 1 with empty state', () => {
    const s = initial()
    expect(s.step).toBe(1)
    expect(s.file).toBeNull()
    expect(s.preview).toBeNull()
    expect(s.formatId).toBeNull()
    expect(s.outputExt).toBe('docx')
    expect(s.priceAdjustPct).toBe(0)
    expect(s.result).toBeNull()
    expect(s.errorMessage).toBeNull()
    expect(s.isWorking).toBe(false)
  })

  it('advances step via setStep', () => {
    initial().setStep(3)
    expect(useNewQuoteStore.getState().step).toBe(3)
  })

  it('stores a staged file', () => {
    const fake = new File(['hi'], 'quote.pdf', { type: 'application/pdf' })
    initial().setFile(fake)
    expect(useNewQuoteStore.getState().file).toBe(fake)
  })

  it('stores preview + raw parsed data together', () => {
    const preview = { recipient_name: 'ABC', sections: [] }
    const raw = { foo: 1 }
    initial().setPreview(preview as never, raw)
    const s = useNewQuoteStore.getState()
    expect(s.preview).toEqual(preview)
    expect(s.parsedRaw).toEqual(raw)
  })

  it('toggles output extension and adjusts price', () => {
    initial().setOutputExt('pdf')
    initial().setPriceAdjustPct(10)
    const s = useNewQuoteStore.getState()
    expect(s.outputExt).toBe('pdf')
    expect(s.priceAdjustPct).toBe(10)
  })

  it('tracks isWorking + error message', () => {
    initial().setWorking(true)
    initial().setError('boom')
    const s = useNewQuoteStore.getState()
    expect(s.isWorking).toBe(true)
    expect(s.errorMessage).toBe('boom')
  })

  it('reset wipes every slice back to defaults', () => {
    const s = initial()
    s.setStep(4)
    s.setFile(new File(['x'], 'x.pdf'))
    s.setFormat('fmt-1')
    s.setPriceAdjustPct(15)
    s.setError('nope')
    s.reset()
    const after = useNewQuoteStore.getState()
    expect(after.step).toBe(1)
    expect(after.file).toBeNull()
    expect(after.formatId).toBeNull()
    expect(after.priceAdjustPct).toBe(0)
    expect(after.errorMessage).toBeNull()
  })
})

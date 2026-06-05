//genai: Sprint 3 / WS-H — Client wizard wrapper. Pulls step from the Zustand
//        store and renders the matching step component.
'use client'

import { Step1Drop } from '@/components/quote/step-1-drop'
import { Step2Confirm } from '@/components/quote/step-2-confirm'
import { Step3Format } from '@/components/quote/step-3-format'
import { Step4Done } from '@/components/quote/step-4-done'
import { WizardProgress } from '@/components/quote/wizard-progress'
import type { SisterFormatOut } from '@/lib/types'
import { useNewQuoteStore } from '@/lib/store/new-quote-store'

export function NewQuoteWizard({ formats }: { formats: SisterFormatOut[] }) {
  const step = useNewQuoteStore((s) => s.step)
  return (
    <div className="animate-fade-in">
      <WizardProgress current={step} />
      {step === 1 ? <Step1Drop /> : null}
      {step === 2 ? <Step2Confirm /> : null}
      {step === 3 ? <Step3Format formats={formats} /> : null}
      {step === 4 ? <Step4Done /> : null}
    </div>
  )
}

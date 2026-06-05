//genai: Background removal — thin client wrapper. Single input (image), single
//        output (transparent PNG). The U-2-Net model is warmed up at API
//        startup and persisted in a Docker volume, so cuts are typically
//        instant from the user's perspective.
'use client'

import { Sparkles } from 'lucide-react'

import { Alert } from '@/components/ui/alert'
import { ProcessRunner } from '@/components/quote/process-runner'

export function BgRemoveForm() {
  return (
    <ProcessRunner
      feature="bg_remove"
      title="Remove background"
      description="Strip the background from product or equipment photos so they're catalog-ready."
      accept={['.png', '.jpg', '.jpeg', '.webp']}
      hint="PNG, JPG, or WEBP. ≤ 15 MB. Output is a transparent PNG."
      submitLabel="Remove background"
      extra={
        <Alert tone="info" title="AI-powered cut-outs">
          <span className="inline-flex items-start gap-2">
            <Sparkles className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden />
            <span>
              We use U-2-Net for clean edges on product and equipment photos.
              Cut-outs usually finish in a few seconds.
            </span>
          </span>
        </Alert>
      }
    />
  )
}

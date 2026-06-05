//genai: Sprint 4 / WS-I — /settings/branding page (logo upload + preview).
import Image from 'next/image'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { requireMe } from '@/lib/auth'

import { LogoUploader } from './logo-uploader'

export const metadata = { title: 'Settings · Branding' }

export default async function BrandingPage() {
  const me = await requireMe()
  const logoUrl = me.company_profile?.logo_url
  return (
    <Card>
      <CardHeader>
        <CardTitle>Branding & logo</CardTitle>
        <p className="mt-1 text-sm text-ink-500">
          Your logo appears in the header of every branded quote and invoice.
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        {logoUrl ? (
          <div className="rounded-xl border border-ink-100 p-4">
            <p className="mb-2 text-sm font-medium text-ink-700">Current logo</p>
            <div className="relative h-24 w-48 overflow-hidden rounded bg-ink-100/50">
              <Image
                src={logoUrl}
                alt="Company logo"
                fill
                className="object-contain"
                sizes="200px"
                unoptimized
              />
            </div>
          </div>
        ) : (
          <p className="text-sm text-ink-500">
            No logo uploaded yet. Pick one below — square logos look best.
          </p>
        )}
        <LogoUploader />
      </CardContent>
    </Card>
  )
}

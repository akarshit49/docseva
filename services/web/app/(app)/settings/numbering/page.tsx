//genai: Sprint 4 / WS-I — /settings/numbering page.
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { requireMe } from '@/lib/auth'

import { NumberingForm } from './numbering-form'

export const metadata = { title: 'Settings · Numbering' }

export default async function NumberingPage() {
  const me = await requireMe()
  return (
    <Card>
      <CardHeader>
        <CardTitle>Document numbering</CardTitle>
        <p className="mt-1 text-sm text-ink-500">
          Customize the prefix that goes in front of each invoice, PO, and quotation
          number. Counters increment automatically.
        </p>
      </CardHeader>
      <CardContent>
        <NumberingForm initial={me.company_profile} />
      </CardContent>
    </Card>
  )
}

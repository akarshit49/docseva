//genai: Sprint 4 / WS-I — /settings/bank page.
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { requireMe } from '@/lib/auth'

import { BankForm } from './bank-form'

export const metadata = { title: 'Settings · Bank' }

export default async function BankPage() {
  const me = await requireMe()
  return (
    <Card>
      <CardHeader>
        <CardTitle>Bank details</CardTitle>
        <p className="mt-1 text-sm text-ink-500">
          Shown on invoices to help your customers pay you faster.
        </p>
      </CardHeader>
      <CardContent>
        <BankForm initial={me.company_profile} />
      </CardContent>
    </Card>
  )
}

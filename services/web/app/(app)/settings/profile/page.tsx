//genai: Sprint 4 / WS-I — /settings/profile page.
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { requireMe } from '@/lib/auth'

import { ProfileForm } from './profile-form'

export const metadata = { title: 'Settings · Profile' }

export default async function ProfileSettingsPage() {
  const me = await requireMe()
  return (
    <Card>
      <CardHeader>
        <CardTitle>Company profile</CardTitle>
        <p className="mt-1 text-sm text-ink-500">
          These details appear on every quote, invoice, and PO you generate.
        </p>
      </CardHeader>
      <CardContent>
        <ProfileForm initial={me.company_profile} />
      </CardContent>
    </Card>
  )
}

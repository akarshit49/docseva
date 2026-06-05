//genai: Sprint 4 / WS-I — /settings/team. Multi-user is Phase 2 — show placeholder.
import { Users } from 'lucide-react'

import { Alert } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export const metadata = { title: 'Settings · Team' }

export default function TeamPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="h-5 w-5 text-brand" aria-hidden /> Team
        </CardTitle>
        <p className="mt-1 text-sm text-ink-500">
          Invite teammates so they can issue quotes under the same organization.
        </p>
      </CardHeader>
      <CardContent>
        <Alert tone="info" title="Multi-user lands in Phase 2">
          For now every organization has a single owner. We're enabling roles
          (Owner, Admin, Sales) in the next release.
        </Alert>
      </CardContent>
    </Card>
  )
}

//genai: Sprint 6 — /settings/account: DPDP "right to data" controls.
import { Database, ShieldAlert } from 'lucide-react'

import { Alert } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import { AccountActions } from './account-actions'

export const metadata = { title: 'Settings · Account & data' }

export default function AccountSettingsPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5 text-brand" aria-hidden /> Your data
          </CardTitle>
          <p className="mt-1 text-sm text-ink-500">
            Under India&apos;s Digital Personal Data Protection Act we give you full
            control over the information we hold on you. Use the controls below
            to take a copy or close your account.
          </p>
        </CardHeader>
        <CardContent>
          <AccountActions />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-brand" aria-hidden /> What
            account deletion means
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-ink-600">
          <p>
            Pressing <strong>Delete my account</strong> doesn&apos;t erase your data
            immediately. Instead we mark your organization as{' '}
            <code>deletion_pending</code> and freeze your usage. You have{' '}
            <strong>30 days</strong> to change your mind by emailing{' '}
            <a className="text-brand underline" href="mailto:support@docseva.in">
              support@docseva.in
            </a>
            .
          </p>
          <p>
            After 30 days the following is permanently removed and is{' '}
            <strong>not recoverable</strong>:
          </p>
          <ul className="list-disc pl-5">
            <li>Your user record and login credentials</li>
            <li>All generated documents and their underlying input files</li>
            <li>Saved sister-quotation formats and your uploaded logo</li>
            <li>All linked channels (Telegram, WhatsApp)</li>
            <li>The organization itself, if you are the sole member</li>
          </ul>
          <p>
            We retain anonymous, aggregate analytics (counts of features used) so
            we can keep improving the product, but they cannot be traced back to
            you.
          </p>
        </CardContent>
      </Card>

      <Alert tone="info" title="Multi-user accounts">
        If you&apos;re part of a team account, you can only delete the
        organization once every other member has been removed. Otherwise we
        delete just your user record.
      </Alert>
    </div>
  )
}

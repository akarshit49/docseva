//genai: Sprint 4 / WS-I — /settings/channels — list + add/remove channel links.
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { listChannels } from '@/lib/api'
import { requireMe } from '@/lib/auth'

import { ChannelsList } from './channels-list'

export const metadata = { title: 'Settings · Channels' }

export default async function ChannelsPage() {
  await requireMe()
  const channels = await listChannels().catch(() => [])
  return (
    <Card>
      <CardHeader>
        <CardTitle>Connected channels</CardTitle>
        <p className="mt-1 text-sm text-ink-500">
          DocSeva is the same brain behind your web account, Telegram bot, and (soon)
          WhatsApp bot. Connect your channels here once and they all share the same
          documents, formats, and quota.
        </p>
      </CardHeader>
      <CardContent>
        <ChannelsList initial={channels} />
      </CardContent>
    </Card>
  )
}

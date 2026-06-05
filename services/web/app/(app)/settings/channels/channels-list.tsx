//genai: Sprint 4 / WS-I — channels list with link/unlink flow.
'use client'

import * as React from 'react'
import { useRouter } from 'next/navigation'
import { Globe, Link2, Mail, MessageCircle, Trash2, type LucideIcon } from 'lucide-react'

import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { humanDate } from '@/lib/utils'
import type { ChannelLinkOut, ChannelLinkStartResponse } from '@/lib/types'

const CHANNEL_META: Record<string, { label: string; icon: LucideIcon }> = {
  web: { label: 'Web', icon: Globe },
  telegram: { label: 'Telegram', icon: MessageCircle },
  whatsapp: { label: 'WhatsApp', icon: MessageCircle },
  email: { label: 'Email', icon: Mail },
}

export function ChannelsList({ initial }: { initial: ChannelLinkOut[] }) {
  const router = useRouter()
  const [links, setLinks] = React.useState<ChannelLinkOut[]>(initial)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [linkData, setLinkData] = React.useState<ChannelLinkStartResponse | null>(null)

  async function startLink(channel: 'telegram' | 'whatsapp') {
    setBusy(true)
    setError(null)
    setLinkData(null)
    try {
      const resp = await fetch('/api/proxy/api/v1/channels/web/start-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel }),
      })
      const body = await resp.json()
      if (!resp.ok) throw new Error(body.detail?.user_message || 'Could not start link.')
      setLinkData(body)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function unlink(id: string) {
    if (!confirm('Unlink this channel? You can re-link it any time.')) return
    setBusy(true)
    setError(null)
    try {
      const resp = await fetch(`/api/proxy/api/v1/channels/${id}`, { method: 'DELETE' })
      if (!resp.ok && resp.status !== 204) throw new Error('Could not unlink.')
      setLinks((prev) => prev.filter((l) => l.id !== id))
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      {error ? <Alert tone="danger">{error}</Alert> : null}

      {links.length === 0 ? (
        <p className="text-sm text-ink-500">No channels connected yet.</p>
      ) : (
        <ul className="divide-y divide-ink-100 rounded-xl border border-ink-100">
          {links.map((link) => {
            const meta = CHANNEL_META[link.channel] || CHANNEL_META.web
            return (
              <li key={link.id} className="flex items-center gap-3 px-4 py-3">
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-soft text-brand">
                  <meta.icon className="h-4 w-4" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink-900">
                    {meta.label} · {link.handle}
                  </p>
                  <p className="text-xs text-ink-500">
                    Linked {humanDate(link.created_at)}
                    {link.verified_at ? ' · verified' : ''}
                  </p>
                </div>
                {link.verified_at ? <Badge tone="success">Verified</Badge> : null}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => unlink(link.id)}
                  disabled={busy}
                  aria-label="Unlink"
                >
                  <Trash2 className="h-4 w-4" aria-hidden />
                </Button>
              </li>
            )
          })}
        </ul>
      )}

      <fieldset className="rounded-xl border border-dashed border-ink-300 p-4">
        <legend className="px-2 text-sm font-medium text-ink-900">Add a channel</legend>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => startLink('telegram')} disabled={busy}>
            <Link2 className="h-4 w-4" aria-hidden /> Connect Telegram
          </Button>
          <Button variant="outline" onClick={() => startLink('whatsapp')} disabled={busy}>
            <Link2 className="h-4 w-4" aria-hidden /> Connect WhatsApp
          </Button>
        </div>

        {linkData ? (
          <div className="mt-4 rounded-lg bg-brand-soft p-4 text-sm">
            <p className="font-medium text-ink-900">
              Open your {linkData.channel} bot and send this code:
            </p>
            <p className="mt-2 select-all rounded-md border border-brand/30 bg-white px-3 py-2 text-center font-mono text-lg tracking-wider">
              {linkData.token}
            </p>
            {linkData.deep_link ? (
              <p className="mt-3 text-center">
                <a href={linkData.deep_link} target="_blank" rel="noreferrer" className="text-brand">
                  Or open the bot directly →
                </a>
              </p>
            ) : null}
            <p className="mt-2 text-xs text-ink-500">
              The code expires in {Math.round(linkData.expires_in / 60)} minutes.
            </p>
          </div>
        ) : null}
      </fieldset>
    </div>
  )
}

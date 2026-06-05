//genai: Sprint 4 / WS-I — /tools index. Small grid of every tool with status badge.
import Link from 'next/link'
import {
  ArrowRight,
  Brush,
  FileBadge,
  FileSpreadsheet,
  Files,
  ImageOff,
  Scale,
  ShieldCheck,
  Wand2,
  type LucideIcon,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { requireMe } from '@/lib/auth'

export const metadata = { title: 'Tools' }

interface Tool {
  href: string
  icon: LucideIcon
  title: string
  description: string
  status: 'live' | 'beta' | 'soon'
}

const TOOLS: Tool[] = [
  {
    href: '/tools/compare',
    icon: Scale,
    title: 'Quotation comparison',
    description: 'Pick a vendor between 2–10 supplier quotes side-by-side.',
    status: 'live',
  },
  {
    href: '/tools/gst-validate',
    icon: ShieldCheck,
    title: 'GST invoice validator',
    description: 'Catch HSN, math, and format issues before you send.',
    status: 'live',
  },
  {
    href: '/tools/convert',
    icon: FileSpreadsheet,
    title: 'Quote → invoice',
    description: 'Convert a generated quote into a GST-ready invoice.',
    status: 'live',
  },
  {
    href: '/tools/watermark',
    icon: Brush,
    title: 'Watermark',
    description: 'Stamp your logo or custom text across product photos.',
    status: 'live',
  },
  {
    href: '/tools/bg-remove',
    icon: ImageOff,
    title: 'Background removal',
    description: 'AI cut-outs for product and equipment photos. Transparent PNG.',
    status: 'live',
  },
  {
    href: '/tools/catalog',
    icon: Files,
    title: 'Product catalog',
    description: 'One-page branded PDF for a product — share over WhatsApp instantly.',
    status: 'live',
  },
]

export default async function ToolsIndexPage() {
  await requireMe()
  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-ink-900">Tools</h1>
        <p className="text-sm text-ink-500">
          Everything DocSeva can do — beyond the anchor flow.
        </p>
      </div>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {TOOLS.map((tool) => (
          <li key={tool.href}>
            <Link
              href={tool.status === 'soon' ? '#' : tool.href}
              aria-disabled={tool.status === 'soon'}
              className={tool.status === 'soon' ? 'pointer-events-none' : ''}
            >
              <Card className={`h-full transition-shadow ${tool.status !== 'soon' ? 'hover:shadow-md' : 'opacity-60'}`}>
                <CardContent className="flex h-full flex-col gap-3 py-5">
                  <div className="flex items-center justify-between">
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-brand-soft text-brand">
                      <tool.icon className="h-4 w-4" aria-hidden />
                    </span>
                    <StatusBadge status={tool.status} />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-ink-900">{tool.title}</p>
                    <p className="mt-1 text-xs text-ink-500">{tool.description}</p>
                  </div>
                  {tool.status !== 'soon' ? (
                    <span className="inline-flex items-center gap-1 text-xs text-brand">
                      Open <ArrowRight className="h-3 w-3" aria-hidden />
                    </span>
                  ) : (
                    <span className="text-xs text-ink-500">Coming soon</span>
                  )}
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>

      <Card className="mt-8 bg-brand-soft/50">
        <CardContent className="flex items-center gap-3 py-5">
          <Wand2 className="h-5 w-5 text-brand" aria-hidden />
          <div className="flex-1 text-sm">
            <p className="font-medium text-ink-900">
              Looking for the anchor flow?
            </p>
            <p className="text-ink-500">
              Supplier quote → your branded quote lives on its own page.
            </p>
          </div>
          <Link href="/new-quote" className="text-sm font-medium text-brand">
            <FileBadge className="mr-1 inline h-4 w-4" aria-hidden />
            Open
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}

function StatusBadge({ status }: { status: 'live' | 'beta' | 'soon' }) {
  if (status === 'live') return <Badge tone="success">Live</Badge>
  if (status === 'beta') return <Badge tone="warning">Beta</Badge>
  return <Badge tone="neutral">Soon</Badge>
}

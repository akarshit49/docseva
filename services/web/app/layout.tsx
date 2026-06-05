//genai: Sprint 3 / WS-F — Root layout. Sets metadata + global font.
import type { Metadata } from 'next'

import './globals.css'

export const metadata: Metadata = {
  title: {
    default: 'DocSeva — Supplier quote → your branded customer quote in 2 min',
    template: '%s · DocSeva',
  },
  description:
    'DocSeva turns supplier quotes into your branded customer quotes — for dealers, traders, and manufacturers of scientific, lab, industrial, medical, and electrical instruments.',
  metadataBase: new URL('https://docseva.in'),
  openGraph: {
    title: 'DocSeva',
    description:
      'Supplier quote → your branded customer quote in under 2 minutes.',
    type: 'website',
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  )
}

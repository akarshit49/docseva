//genai: Shared shell for every /tools/<name> page.
//
// Renders a breadcrumb ("Tools › <title>") above the page heading so users
// always have a one-click route back to the tools index. This also removes the
// duplicated header markup that lived in each individual tool page.
import * as React from 'react'
import Link from 'next/link'
import { ChevronRight } from 'lucide-react'

interface ToolPageShellProps {
  title: string
  description: React.ReactNode
  children: React.ReactNode
}

export function ToolPageShell({ title, description, children }: ToolPageShellProps) {
  return (
    <div className="mx-auto max-w-3xl">
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="mb-5 flex items-center gap-1.5 text-sm">
        <Link
          href="/tools"
          className="text-ink-500 transition-colors hover:text-brand"
        >
          Tools
        </Link>
        <ChevronRight className="h-3.5 w-3.5 text-ink-300" aria-hidden />
        <span className="font-medium text-ink-900">{title}</span>
      </nav>

      {/* Page heading */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-900">{title}</h1>
        <p className="mt-1 text-sm text-ink-500">{description}</p>
      </div>

      {children}
    </div>
  )
}

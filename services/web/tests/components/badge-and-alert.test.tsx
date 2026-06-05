//genai: Sprint 6 follow-up — Badge + Alert visual smoke.
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'

describe('<Badge />', () => {
  it('renders children with the brand tone classes', () => {
    render(<Badge tone="brand">Pro</Badge>)
    const el = screen.getByText('Pro')
    expect(el).toBeInTheDocument()
    expect(el.className).toContain('bg-brand-soft')
  })

  it('defaults to neutral tone', () => {
    render(<Badge>Plain</Badge>)
    expect(screen.getByText('Plain').className).toContain('bg-ink-100')
  })
})

describe('<Alert />', () => {
  it('renders title + body and sets role="alert"', () => {
    render(
      <Alert tone="success" title="Saved">
        Everything is fine
      </Alert>,
    )
    const alert = screen.getByRole('alert')
    expect(alert).toBeInTheDocument()
    expect(screen.getByText('Saved')).toBeInTheDocument()
    expect(screen.getByText(/everything is fine/i)).toBeInTheDocument()
  })

  it('applies danger styles for the danger tone', () => {
    render(<Alert tone="danger">Boom</Alert>)
    expect(screen.getByRole('alert').className).toContain('border-danger')
  })
})

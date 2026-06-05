//genai: Sprint 6 follow-up — Button primitive smoke tests.
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { Button } from '@/components/ui/button'

describe('<Button />', () => {
  it('renders children and forwards clicks', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Click me</Button>)
    const btn = screen.getByRole('button', { name: /click me/i })
    expect(btn).toBeInTheDocument()
    await userEvent.click(btn)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('applies the danger variant class', () => {
    render(<Button variant="danger">Delete</Button>)
    const btn = screen.getByRole('button', { name: /delete/i })
    // Variant classes come from CVA; check we emit a known danger token.
    expect(btn.className).toContain('bg-danger')
  })

  it('respects the disabled attribute', async () => {
    const onClick = vi.fn()
    render(
      <Button disabled onClick={onClick}>
        Save
      </Button>,
    )
    const btn = screen.getByRole('button', { name: /save/i })
    expect(btn).toBeDisabled()
    await userEvent.click(btn).catch(() => {})
    expect(onClick).not.toHaveBeenCalled()
  })
})

import { describe, expect, it, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Footer } from './Footer'

describe('Footer', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('computes the copyright year dynamically rather than hardcoding it', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2031, 0, 1))

    render(<Footer />)

    expect(screen.getByText((text) => text.includes('© 2031'))).toBeInTheDocument()
    expect(screen.queryByText((text) => text.includes('2026') && text.includes('©'))).not.toBeInTheDocument()
  })

  it('shows TradeLens AI and the maker signature', () => {
    render(<Footer />)
    expect(screen.getByText((text) => text.includes('TradeLens AI'))).toBeInTheDocument()
    expect(screen.getByText((text) => text.includes('Akshi'))).toBeInTheDocument()
    expect(screen.getByText((text) => text.includes('👩‍💻'))).toBeInTheDocument()
  })
})

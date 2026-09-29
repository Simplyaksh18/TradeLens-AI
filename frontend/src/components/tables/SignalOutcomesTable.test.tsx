import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SignalOutcomesTable } from './SignalOutcomesTable'
import type { SignalOutcome } from '../../api/types'

function outcome(date: string, overrides: Partial<SignalOutcome> = {}): SignalOutcome {
  return {
    date,
    decision: 'BUY',
    reference_close: 100,
    forward_close_5d: 105,
    forward_return_5d: 0.05,
    forward_close_10d: 110,
    forward_return_10d: 0.1,
    mae_10d: -0.03,
    mfe_10d: 0.12,
    available_forward_bars: 14,
    ...overrides,
  }
}

describe('SignalOutcomesTable', () => {
  it('shows the empty state when there are no outcomes', () => {
    render(<SignalOutcomesTable outcomes={[]} />)
    expect(screen.getByText('No BUY signal outcomes in this period.')).toBeInTheDocument()
  })

  it('uses "Reference Close" terminology, never "Entry Price"', () => {
    render(<SignalOutcomesTable outcomes={[outcome('2024-01-05')]} />)
    expect(screen.getByText('Reference Close')).toBeInTheDocument()
    expect(screen.queryByText(/entry price/i)).not.toBeInTheDocument()
  })

  it('renders censored (null) future metrics as the placeholder, never 0', () => {
    const censored = outcome('2024-06-20', {
      forward_close_5d: null,
      forward_return_5d: null,
      forward_close_10d: null,
      forward_return_10d: null,
      mae_10d: null,
      mfe_10d: null,
      available_forward_bars: 3,
    })
    render(<SignalOutcomesTable outcomes={[censored]} />)
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBe(6) // one per censored field
    expect(screen.queryByText(/^0\.00%$/)).not.toBeInTheDocument()
  })

  it('preserves consecutive BUY outcomes as separate rows, never collapsed', () => {
    const outcomes = [outcome('2024-01-05'), outcome('2024-01-06'), outcome('2024-01-07')]
    render(<SignalOutcomesTable outcomes={outcomes} />)
    expect(screen.getAllByRole('row')).toHaveLength(4) // header + 3 separate outcome rows
  })
})

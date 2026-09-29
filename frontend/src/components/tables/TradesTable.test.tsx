import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { TradesTable } from './TradesTable'
import type { ExecutedTrade } from '../../api/types'

const TRADE: ExecutedTrade = {
  entry_signal_date: '2024-01-05',
  entry_date: '2024-01-08',
  entry_price: 110,
  exit_signal_date: '2024-01-20',
  exit_date: '2024-01-22',
  exit_price: 130,
  quantity: 9,
  gross_pnl: 180,
  gross_return: 0.18181818181818188,
  net_pnl: 180,
}

describe('TradesTable', () => {
  it('shows the empty state when there are no closed trades', () => {
    render(<TradesTable trades={[]} />)
    expect(screen.getByText('No closed trades in this period.')).toBeInTheDocument()
  })

  it('renders all accepted trade fields', () => {
    render(<TradesTable trades={[TRADE]} />)
    const row = screen.getByRole('row', { name: /05 Jan 2024/ })
    expect(within(row).getByText(/08 Jan 2024/)).toBeInTheDocument()
    expect(within(row).getByText(/20 Jan 2024/)).toBeInTheDocument()
    expect(within(row).getByText(/22 Jan 2024/)).toBeInTheDocument()
    expect(within(row).getByText('9')).toBeInTheDocument()
  })

  it('never inserts a row for an open position (caller controls that)', () => {
    render(<TradesTable trades={[TRADE]} />)
    expect(screen.getAllByRole('row')).toHaveLength(2) // header + 1 trade row only
  })
})

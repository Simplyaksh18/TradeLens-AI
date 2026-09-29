import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { OHLCVTable } from './OHLCVTable'
import type { OHLCVBar } from '../../api/types'

const BARS: OHLCVBar[] = [
  { date: '2026-01-01', open: 100, high: 105, low: 99, close: 102, adj_close: 95, volume: 0 },
  { date: '2026-01-02', open: 111, high: 118, low: 109, close: 116, adj_close: 108.5, volume: 12000 },
]

describe('OHLCVTable', () => {
  it('renders raw Close and Adj Close as distinct values in the same row', () => {
    render(<OHLCVTable bars={BARS} />)
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getByText('102.00')).toBeInTheDocument() // raw close
    expect(within(rows[0]).getByText('95.00')).toBeInTheDocument() // adj_close, deliberately different
  })

  it('renders a zero-volume row as zero, never blank or dropped', () => {
    render(<OHLCVTable bars={BARS} />)
    const rows = screen.getAllByRole('row')
    // header + 2 data rows
    expect(rows).toHaveLength(3)
    expect(within(rows[1]).getByText('0')).toBeInTheDocument()
  })

  it('preserves row order matching input order', () => {
    render(<OHLCVTable bars={BARS} />)
    const rows = screen.getAllByRole('row').slice(1) // drop header
    expect(rows[0].textContent).toContain('01 Jan 2026')
    expect(rows[1].textContent).toContain('02 Jan 2026')
  })
})

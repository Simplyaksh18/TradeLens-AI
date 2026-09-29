import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EvidenceInspector } from './EvidenceInspector'
import type { StrategyEvaluation } from '../../api/types'

const BUY_EVALUATION: StrategyEvaluation = {
  date: '2026-09-18',
  strategy_id: 'trend_momentum_v1',
  strategy_name: 'Trend + Momentum v1',
  decision: 'BUY',
  missing_inputs: [],
  conditions: [
    {
      condition_id: 'close_above_sma20',
      description: 'Close is above SMA20',
      passed: true,
      operator: '>',
      actual_values: [
        { name: 'close', value: 1284.5 },
        { name: 'sma20', value: 1261.32 },
      ],
      reference_values: [],
    },
    {
      condition_id: 'sma20_above_sma50',
      description: 'SMA20 is above SMA50',
      passed: true,
      operator: '>',
      actual_values: [
        { name: 'sma20', value: 1261.32 },
        { name: 'sma50', value: 1242.81 },
      ],
      reference_values: [],
    },
    {
      condition_id: 'rsi_in_range',
      description: 'RSI14 is within the inclusive strategy range',
      passed: false,
      operator: 'inclusive_range',
      actual_values: [{ name: 'rsi14', value: 73.4 }],
      reference_values: [
        { name: 'lower_bound', value: 40 },
        { name: 'upper_bound', value: 70 },
      ],
    },
  ],
}

const INSUFFICIENT_EVALUATION: StrategyEvaluation = {
  date: '2026-01-05',
  strategy_id: 'trend_momentum_v1',
  strategy_name: 'Trend + Momentum v1',
  decision: 'INSUFFICIENT_DATA',
  missing_inputs: ['sma50'],
  conditions: [],
}

describe('EvidenceInspector', () => {
  it('renders conditions in the stable backend order', () => {
    render(<EvidenceInspector evaluation={BUY_EVALUATION} />)
    const headings = screen.getAllByText(/Close is above SMA20|SMA20 is above SMA50|RSI14 is within/)
    expect(headings.map((h) => h.textContent)).toEqual([
      'Close is above SMA20',
      'SMA20 is above SMA50',
      'RSI14 is within the inclusive strategy range',
    ])
  })

  it('renders numeric evidence exactly as supplied by the API payload', () => {
    render(<EvidenceInspector evaluation={BUY_EVALUATION} />)
    expect(screen.getByText('1,284.50')).toBeInTheDocument()
    // 1,261.32 (sma20) legitimately appears in both C1's and C2's evidence
    expect(screen.getAllByText('1,261.32')).toHaveLength(2)
    expect(screen.getByText('1,242.81')).toBeInTheDocument()
    expect(screen.getByText('73.40')).toBeInTheDocument()
    expect(screen.getByText('40.00')).toBeInTheDocument()
    expect(screen.getByText('70.00')).toBeInTheDocument()
  })

  it('renders INSUFFICIENT_DATA as a distinct state, never as NO_SIGNAL, with zero conditions', () => {
    render(<EvidenceInspector evaluation={INSUFFICIENT_EVALUATION} />)
    expect(screen.getByText(/not enough history/i)).toBeInTheDocument()
    expect(screen.getByText(/sma50/i)).toBeInTheDocument()
    expect(screen.queryByText('SMA20 is above SMA50')).not.toBeInTheDocument()
  })

  it('never invents SELL UI', () => {
    const { container } = render(<EvidenceInspector evaluation={BUY_EVALUATION} />)
    expect(container.textContent ?? '').not.toMatch(/sell/i)
  })
})

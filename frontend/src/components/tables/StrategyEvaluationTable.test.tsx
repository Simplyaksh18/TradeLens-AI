import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StrategyEvaluationTable } from './StrategyEvaluationTable'
import type { StrategyEvaluation } from '../../api/types'

const SUFFICIENT: StrategyEvaluation = {
  date: '2026-03-09',
  strategy_id: 'trend_momentum_v1',
  strategy_name: 'Trend + Momentum v1',
  decision: 'BUY',
  missing_inputs: [],
  conditions: [
    { condition_id: 'close_above_sma20', description: 'Close is above SMA20', passed: true, operator: '>', actual_values: [], reference_values: [] },
    { condition_id: 'sma20_above_sma50', description: 'SMA20 is above SMA50', passed: true, operator: '>', actual_values: [], reference_values: [] },
    { condition_id: 'rsi_in_range', description: 'RSI in range', passed: true, operator: 'inclusive_range', actual_values: [], reference_values: [] },
  ],
}

const INSUFFICIENT: StrategyEvaluation = {
  date: '2026-01-05',
  strategy_id: 'trend_momentum_v1',
  strategy_name: 'Trend + Momentum v1',
  decision: 'INSUFFICIENT_DATA',
  missing_inputs: ['sma20', 'sma50', 'rsi14'],
  conditions: [],
}

function getTable() {
  return screen.getByRole('table')
}

function getFilterGroup() {
  return screen.getByRole('group', { name: 'Filter by decision' })
}

describe('StrategyEvaluationTable', () => {
  it('preserves BUY/NO_SIGNAL/INSUFFICIENT_DATA distinctly per row', () => {
    render(<StrategyEvaluationTable evaluations={[INSUFFICIENT, SUFFICIENT]} />)
    expect(within(getTable()).getByText('Insufficient Data')).toBeInTheDocument()
    expect(within(getTable()).getByText('Buy')).toBeInTheDocument()
  })

  it('calls onSelect only for sufficient-data rows', async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()
    render(<StrategyEvaluationTable evaluations={[INSUFFICIENT, SUFFICIENT]} onSelect={onSelect} />)

    await user.click(within(getTable()).getByText('Insufficient Data'))
    expect(onSelect).not.toHaveBeenCalled()

    await user.click(within(getTable()).getByText('Buy'))
    expect(onSelect).toHaveBeenCalledWith(SUFFICIENT)
  })

  it('never renders SELL UI', () => {
    const { container } = render(<StrategyEvaluationTable evaluations={[SUFFICIENT]} />)
    expect(container.textContent ?? '').not.toMatch(/sell/i)
  })

  it('shows INSUFFICIENT_DATA by default (not hidden behind a filter)', () => {
    render(<StrategyEvaluationTable evaluations={[INSUFFICIENT, SUFFICIENT]} />)
    expect(screen.getByText('2 of 2 rows')).toBeInTheDocument()
  })

  it('filtering to BUY only changes what is displayed, not the underlying data', async () => {
    const user = userEvent.setup()
    render(<StrategyEvaluationTable evaluations={[INSUFFICIENT, SUFFICIENT]} />)

    await user.click(within(getFilterGroup()).getByRole('button', { name: 'Buy' }))

    expect(screen.getByText('1 of 2 rows')).toBeInTheDocument()
    expect(within(getTable()).queryByText('Insufficient Data')).not.toBeInTheDocument()
    expect(within(getTable()).getByText('Buy')).toBeInTheDocument()

    await user.click(within(getFilterGroup()).getByRole('button', { name: 'All' }))
    expect(screen.getByText('2 of 2 rows')).toBeInTheDocument()
    expect(within(getTable()).getByText('Insufficient Data')).toBeInTheDocument()
  })
})

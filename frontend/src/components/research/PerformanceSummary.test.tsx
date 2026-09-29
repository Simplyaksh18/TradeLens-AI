import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PerformanceSummary } from './PerformanceSummary'
import type { PerformanceAnalyticsResponse } from '../../api/types'

function analytics(overrides: Partial<PerformanceAnalyticsResponse> = {}): PerformanceAnalyticsResponse {
  return {
    provider_symbol: 'RELIANCE.NS',
    interval: '1d',
    strategy_id: 'trend_momentum_v1',
    strategy_name: 'Trend + Momentum v1',
    initial_equity: 100000,
    ending_equity: 102139.47,
    total_return: 0.0213947,
    realized_pnl: -5618.27,
    unrealized_pnl: 7757.75,
    total_pnl: 2139.47,
    closed_trade_count: 4,
    winner_count: 0,
    loser_count: 4,
    breakeven_count: 0,
    win_rate: 0.0,
    average_trade_return: -0.05,
    median_trade_return: -0.04,
    best_trade_return: -0.01,
    worst_trade_return: -0.09,
    peak_equity: 102139.47,
    maximum_drawdown: -0.0561827,
    max_drawdown_peak_date: '2024-03-01',
    max_drawdown_trough_date: '2024-04-01',
    exposed_bar_count: 100,
    total_bar_count: 120,
    exposure: 0.8333,
    drawdown_series: [],
    ...overrides,
  }
}

describe('PerformanceSummary', () => {
  it('formats decimal return as a signed percentage for display only', () => {
    render(<PerformanceSummary analytics={analytics()} />)
    expect(screen.getByText('+2.14%')).toBeInTheDocument()
  })

  it('renders negative maximum drawdown as negative, never flipped positive', () => {
    render(<PerformanceSummary analytics={analytics()} />)
    expect(screen.getByText('-5.62%')).toBeInTheDocument()
  })

  it('renders a zero win rate as 0.00%, not the null placeholder', () => {
    render(<PerformanceSummary analytics={analytics({ win_rate: 0.0 })} />)
    expect(screen.getByText('0.00%')).toBeInTheDocument()
  })

  it('renders a null win rate as the placeholder, not 0%', () => {
    render(<PerformanceSummary analytics={analytics({ win_rate: null })} />)
    const winRateTile = screen.getByText('Win Rate').parentElement!
    expect(winRateTile.textContent).toContain('—')
  })

  it('uses accepted API values directly (no recomputation) for closed trade count and exposure', () => {
    render(<PerformanceSummary analytics={analytics()} />)
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('83.33%')).toBeInTheDocument()
  })
})

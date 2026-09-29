import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { OpenPositionPanel } from './OpenPositionPanel'
import type { BacktestResultResponse, PerformanceAnalyticsResponse } from '../../api/types'

function backtest(overrides: Partial<BacktestResultResponse> = {}): BacktestResultResponse {
  return {
    provider_symbol: 'RELIANCE.NS',
    interval: '1d',
    strategy_id: 'trend_momentum_v1',
    strategy_name: 'Trend + Momentum v1',
    config: { initial_capital: 100000, transaction_cost: 0, slippage: 0 },
    trades: [],
    open_position: null,
    pending_entry_signal_date: null,
    equity_curve: [],
    ...overrides,
  }
}

const ANALYTICS = { unrealized_pnl: 7757.75 } as PerformanceAnalyticsResponse

describe('OpenPositionPanel', () => {
  it('shows "no open position" when there is none', () => {
    render(<OpenPositionPanel backtest={backtest()} analytics={null} />)
    expect(screen.getByText('No open position at end of selected period.')).toBeInTheDocument()
  })

  it('shows OPEN status with fields and unrealized P&L from analytics (never computed here)', () => {
    render(
      <OpenPositionPanel
        backtest={backtest({
          open_position: {
            entry_signal_date: '2024-06-10',
            entry_date: '2024-06-11',
            entry_price: 1200,
            quantity: 80,
            pending_exit_signal_date: null,
          },
        })}
        analytics={ANALYTICS}
      />,
    )
    expect(screen.getByText('Status: OPEN')).toBeInTheDocument()
    expect(screen.getByText(/7,757\.75/)).toBeInTheDocument()
    expect(screen.getByText('80')).toBeInTheDocument()
  })

  it('shows a Pending Entry Signal explanation, not an error, without implying execution', () => {
    render(<OpenPositionPanel backtest={backtest({ pending_entry_signal_date: '2024-06-28' })} analytics={null} />)
    expect(screen.getByText(/Pending Entry Signal/)).toBeInTheDocument()
    expect(screen.getByText(/no next trading bar was available for execution/i)).toBeInTheDocument()
  })

  it('shows a Pending Exit Signal explanation on an otherwise-open position', () => {
    render(
      <OpenPositionPanel
        backtest={backtest({
          open_position: {
            entry_signal_date: '2024-06-10',
            entry_date: '2024-06-11',
            entry_price: 1200,
            quantity: 80,
            pending_exit_signal_date: '2024-06-30',
          },
        })}
        analytics={ANALYTICS}
      />,
    )
    expect(screen.getByText(/Pending Exit Signal/)).toBeInTheDocument()
    expect(screen.getByText('Status: OPEN')).toBeInTheDocument()
  })
})

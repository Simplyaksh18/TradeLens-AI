import { apiGet } from './client'
import type { BacktestResultResponse } from './types'
import type { HistoryRequest } from './marketData'

export const TREND_MOMENTUM_V1 = 'trend-momentum-v1'

export interface BacktestRequest extends HistoryRequest {
  initialCapital: number
}

export function getTrendMomentumV1Backtest({
  symbol,
  start,
  end,
  interval = '1d',
  initialCapital,
  signal,
}: BacktestRequest): Promise<BacktestResultResponse> {
  return apiGet<BacktestResultResponse>(`/api/v1/backtests/${TREND_MOMENTUM_V1}/${encodeURIComponent(symbol)}`, {
    params: { start, end, interval, initial_capital: initialCapital },
    signal,
  })
}

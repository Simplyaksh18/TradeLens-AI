import { apiGet } from './client'
import type { PerformanceAnalyticsResponse } from './types'
import type { BacktestRequest } from './backtests'

export const TREND_MOMENTUM_V1 = 'trend-momentum-v1'

export function getTrendMomentumV1Analytics({
  symbol,
  start,
  end,
  interval = '1d',
  initialCapital,
  signal,
}: BacktestRequest): Promise<PerformanceAnalyticsResponse> {
  return apiGet<PerformanceAnalyticsResponse>(`/api/v1/analytics/${TREND_MOMENTUM_V1}/${encodeURIComponent(symbol)}`, {
    params: { start, end, interval, initial_capital: initialCapital },
    signal,
  })
}

import { apiGet } from './client'
import type { SignalOutcomeSeriesResponse } from './types'
import type { HistoryRequest } from './marketData'

export const TREND_MOMENTUM_V1 = 'trend-momentum-v1'

export function getTrendMomentumV1Outcomes({
  symbol,
  start,
  end,
  interval = '1d',
  signal,
}: HistoryRequest): Promise<SignalOutcomeSeriesResponse> {
  return apiGet<SignalOutcomeSeriesResponse>(`/api/v1/outcomes/${TREND_MOMENTUM_V1}/${encodeURIComponent(symbol)}`, {
    params: { start, end, interval },
    signal,
  })
}

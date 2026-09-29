import { apiGet } from './client'
import type { StrategyEvaluationSeriesResponse } from './types'
import type { HistoryRequest } from './marketData'

export const TREND_MOMENTUM_V1 = 'trend-momentum-v1'

export function getTrendMomentumV1({ symbol, start, end, interval = '1d', signal }: HistoryRequest): Promise<StrategyEvaluationSeriesResponse> {
  return apiGet<StrategyEvaluationSeriesResponse>(
    `/api/v1/strategies/${TREND_MOMENTUM_V1}/${encodeURIComponent(symbol)}`,
    { params: { start, end, interval }, signal },
  )
}
